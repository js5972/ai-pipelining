"""Minimal OpenAlex client: retries, request log, cost estimate, budget guard, response cache.

Every request goes through OpenAlex.get(), which:
- refuses to send if the estimated cost would pass the run's budget limit,
- retries 429/5xx and network errors with backoff (honouring Retry-After),
- appends one line per request to runs/<id>/request_log.jsonl,
- caches successful responses (cache=True) in runs/<id>/cache.jsonl so --resume never pays twice.
"""
import json
import os
import time

import requests

from .queries import query_id
from .runs import now_utc

RETRYABLE = {429, 500, 502, 503, 504}


class OpenAlexError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class OpenAlex:
    def __init__(self, cfg: dict, run_dir, settings: dict | None = None, session=None):
        """settings overrides cfg['openalex'] (used by retrieval to apply the frozen query's settings)."""
        self.s = {**cfg["openalex"], **(settings or {})}
        key = os.environ.get(self.s["api_key_env"])
        if not key:
            raise RuntimeError(f"Environment variable {self.s['api_key_env']} is not set.")
        self.prices = cfg["prices_usd"]
        b = cfg["budget"]
        self.limit_usd = b["daily_usd"] * b["stop_fraction"] - b["spent_today_usd"]
        self.confirm_above_usd = b["confirm_above_usd"]
        self.base_url = self.s["base_url"].rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})  # key never appears in logged URLs
        self.log_path = run_dir / "request_log.jsonl"
        self.cache_path = run_dir / "cache.jsonl"
        self.cache = self._read_jsonl(self.cache_path, key="query_id", value="data")
        self.spent_usd = sum(e.get("cost_usd") or 0 for e in self._iter_jsonl(self.log_path))

    # ---------- helpers ----------
    @staticmethod
    def _iter_jsonl(path):
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        yield json.loads(line)

    def _read_jsonl(self, path, key, value):
        return {e[key]: e[value] for e in self._iter_jsonl(path)}

    @staticmethod
    def _append(path, obj):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, default=str) + "\n")

    def search_params(self, query: str, **extra) -> dict:
        return {self.s["search_param"]: query, "corpus": self.s["corpus"], **extra}

    @staticmethod
    def request_type(endpoint: str, params: dict) -> str:
        if endpoint.strip("/").count("/") >= 1:      # works/W123, works/doi:10...
            return "singleton"
        if any(k == "search" or k.startswith("search.") for k in params):
            return "search"
        return "list"

    def price(self, endpoint, params) -> float:
        return self.prices[self.request_type(endpoint, params)]

    def remaining_usd(self) -> float:
        return self.limit_usd - self.spent_usd

    def confirm(self, n_requests: int, est_usd: float, assume_yes: bool = False) -> bool:
        """Print the plan; ask before spending more than budget.confirm_above_usd."""
        print(f"Plan: {n_requests} requests, estimated ${est_usd:.4f}; "
              f"remaining before stop threshold ${self.remaining_usd():.4f}")
        if est_usd > self.remaining_usd():
            print("Estimated cost exceeds the remaining budget; the run will stop at the threshold.")
        if est_usd <= self.confirm_above_usd or assume_yes:
            return True
        return input("Proceed? [y/N] ").strip().lower() == "y"

    # ---------- the one request function ----------
    def get(self, endpoint: str, params: dict, label: str = "", cache: bool = True) -> dict:
        qid = query_id(endpoint, params)
        if cache and qid in self.cache:
            return self.cache[qid]

        price = self.price(endpoint, params)
        if price > 0 and self.spent_usd + price > self.limit_usd:
            raise BudgetExceeded(f"Budget threshold reached (spent ~${self.spent_usd:.4f}).")

        url = f"{self.base_url}/{endpoint.strip('/')}"
        retries, t0 = 0, time.perf_counter()
        while True:
            try:
                resp = self.session.get(url, params=params, timeout=self.s["request_timeout_s"])
                status = resp.status_code
            except requests.RequestException as exc:
                resp, status = None, f"exception: {type(exc).__name__}"
            if (resp is None or status in RETRYABLE) and retries < self.s["max_retries"]:
                wait = 2 ** retries
                if resp is not None and str(resp.headers.get("Retry-After", "")).isdigit():
                    wait = int(resp.headers["Retry-After"])
                time.sleep(wait)
                retries += 1
                continue
            break
        wall_ms = round((time.perf_counter() - t0) * 1000)

        data, error = None, None
        if resp is not None:
            try:
                payload = resp.json()
            except ValueError:
                payload, error = None, resp.text[:300]
            if status == 200 and isinstance(payload, dict):
                data = payload
            elif isinstance(payload, dict):
                error = payload.get("message") or payload.get("error") or str(payload)[:300]

        meta = (data or {}).get("meta") or {}
        reported = meta.get("cost")
        if reported is not None:
            cost_usd = reported * self.s["credit_usd"] if self.s["reported_cost_unit"] == "credits" else reported
        else:
            cost_usd = price if status == 200 else 0.0
        self.spent_usd += cost_usd

        self._append(self.log_path, {
            "query_id": qid, "timestamp_utc": now_utc(), "label": label, "endpoint": endpoint,
            "params": params, "url": resp.url if resp is not None else None,
            "request_type": self.request_type(endpoint, params), "status": status, "retries": retries,
            "wall_ms": wall_ms, "db_response_time_ms": meta.get("db_response_time_ms"),
            "count": meta.get("count"), "n_results": len((data or {}).get("results") or []),
            "reported_cost": reported, "cost_usd": cost_usd, "error": error,
        })
        time.sleep(self.s["pause_s"])

        if data is None:
            raise OpenAlexError(f"{status}: {error}")
        if cache:
            self.cache[qid] = data
            self._append(self.cache_path, {"query_id": qid, "data": data})
        return data

    # ---------- convenience ----------
    def count(self, query: str, label: str = "", **extra) -> int:
        params = self.search_params(query, per_page=1, select="id", **extra)
        return self.get("works", params, label=label)["meta"]["count"]

    def count_many(self, items):
        """items: list of (key, query, label). Returns ({key: count or None}, stop_reason).
        Stops on budget or after max_consecutive_failures failures in a row."""
        results, failures, stop = {}, 0, "completed"
        for i, (key, query, label) in enumerate(items, 1):
            try:
                results[key] = self.count(query, label=label)
                failures = 0
            except BudgetExceeded as exc:
                stop = str(exc)
                break
            except OpenAlexError as exc:
                results[key] = None
                failures += 1
                print(f"  failed: {label}: {exc}")
                if failures >= self.s["max_consecutive_failures"]:
                    stop = f"{failures} failures in a row (last: {exc})"
                    break
            if i % 25 == 0:
                print(f"  {i}/{len(items)} done, spent ~${self.spent_usd:.4f}")
        return results, stop

    def count_plan_cost(self, items) -> tuple[int, float]:
        """(requests not yet cached, estimated USD) for a list of (key, query, label)."""
        todo = [q for _, q, _ in items
                if query_id("works", self.search_params(q, per_page=1, select="id")) not in self.cache]
        todo = list(dict.fromkeys(todo))
        return len(todo), len(todo) * self.prices["search"]
