"""Stage 8: retrieve the corpus for the APPROVED query in data/04_query/query.yaml (gate G3).

Phase 1: cursor-page each query with select=id -> ids.txt (de-duplicated across queries).
Phase 2: fetch full records 100 IDs at a time (openalex: filter, list price) -> records_NNN.jsonl.gz.
Both phases checkpoint; re-run with --resume <run_id> after an interruption.
"""
import argparse
import gzip
import json
import math

import yaml

from kwpipe.config import load_config, resolve, sha256_file
from kwpipe.openalex import BudgetExceeded, OpenAlex
from kwpipe.runs import finish_run, start_run


def short_id(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def load_state(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_state(path, state):
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query-file", default="data/04_query/query.yaml")
    ap.add_argument("--resume")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    qf = yaml.safe_load(resolve(args.query_file).read_text(encoding="utf-8"))
    if qf.get("approved") is not True or not qf.get("approved_by"):
        raise SystemExit("Query is not approved (gate G3): set approved: true and approved_by in the query file.")
    if qf.get("keywords_sha256") and resolve(qf["keywords_file"]).exists() \
            and sha256_file(qf["keywords_file"]) != qf["keywords_sha256"]:
        print("WARNING: keywords.csv changed since this query was drafted. The frozen query is used as written.")

    run_dir, meta = start_run("retrieve", cfg, inputs={"query_file": args.query_file},
                              resume=args.resume, params=vars(args))
    oa = OpenAlex(cfg, run_dir, settings=qf["settings"])
    queries = qf["queries"]

    # --- plan ---
    counts = [oa.count(q, label=f"count q{i}") for i, q in enumerate(queries, 1)]
    pages = sum(math.ceil(c / 100) for c in counts)
    batches = math.ceil(sum(counts) / 100)          # upper bound: overlap between chunks reduces it
    est = pages * cfg["prices_usd"]["search"] + batches * cfg["prices_usd"]["list"]
    print(f"Reported counts per query: {counts}")
    if not oa.confirm(pages + batches, est, args.yes):
        return

    # --- phase 1: IDs ---
    stop = "completed"
    try:
        for i, q in enumerate(queries, 1):
            state_path, ids_path = run_dir / f"phase1_q{i}.json", run_dir / f"ids_q{i}.txt"
            state = load_state(state_path, {"cursor": "*", "done": False, "pages": 0})
            while not state["done"]:
                res = oa.get("works", oa.search_params(q, per_page=100, select="id", cursor=state["cursor"]),
                             label=f"ids q{i} page {state['pages'] + 1}", cache=False)
                with open(ids_path, "a", encoding="utf-8") as f:
                    f.writelines(short_id(w["id"]) + "\n" for w in res["results"])
                state["pages"] += 1
                state["cursor"] = res["meta"].get("next_cursor")
                state["done"] = not state["cursor"] or not res["results"]
                save_state(state_path, state)

        ids = []
        for i in range(1, len(queries) + 1):
            ids += (run_dir / f"ids_q{i}.txt").read_text(encoding="utf-8").split()
        ids = sorted(set(ids))
        (run_dir / "ids.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
        print(f"Phase 1: {len(ids)} unique IDs")

        # --- phase 2: records ---
        fields = ",".join(cfg["retrieval"]["fields"])
        per_file = cfg["retrieval"]["records_per_file"]
        state_path = run_dir / "phase2.json"
        state = load_state(state_path, {"done_batches": []})
        n_batches = math.ceil(len(ids) / 100)
        for b in range(n_batches):
            if b in state["done_batches"]:
                continue
            batch = ids[b * 100:(b + 1) * 100]
            res = oa.get("works", {"filter": f"openalex:{'|'.join(batch)}", "per_page": 100, "select": fields,
                                   "corpus": qf["settings"].get("corpus", "core")},
                         label=f"records batch {b + 1}/{n_batches}", cache=False)
            part = run_dir / f"records_{(b * 100) // per_file:03d}.jsonl.gz"
            with gzip.open(part, "at", encoding="utf-8") as f:
                f.writelines(json.dumps(w, ensure_ascii=False) + "\n" for w in res["results"])
            state["done_batches"].append(b)
            save_state(state_path, state)
    except BudgetExceeded as exc:
        stop = f"{exc} Re-run tomorrow with --resume {run_dir.name}."
        print(stop)

    # --- verification ---
    summary = {"stop_reason": stop, "reported_counts": counts, "spent_usd": round(oa.spent_usd, 4)}
    if stop == "completed":
        got, with_abstract = set(), 0
        for part in sorted(run_dir.glob("records_*.jsonl.gz")):
            with gzip.open(part, "rt", encoding="utf-8") as f:
                for line in f:
                    w = json.loads(line)
                    if short_id(w["id"]) not in got:
                        got.add(short_id(w["id"]))
                        with_abstract += bool(w.get("abstract_inverted_index"))
        missing = sorted(set(ids) - got)
        (run_dir / "missing_ids.txt").write_text("\n".join(missing) + "\n", encoding="utf-8")
        summary.update({"unique_ids": len(ids), "records": len(got), "missing_ids": len(missing),
                        "share_with_abstract": round(with_abstract / max(len(got), 1), 3)})
    finish_run(run_dir, meta, summary)


if __name__ == "__main__":
    main()
