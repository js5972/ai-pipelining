import json

import pytest

# Fake OpenAlex corpus: which work IDs each search term matches.
TERM_HITS = {
    '"green bond"': set(range(0, 8000)),
    '"climate bond"': set(range(7700, 8600)),        # 900 works, 600 new  -> niche
    '"green bonds"': set(range(0, 5000)),            # fully inside P       -> redundant
    "greenium": set(range(20000, 20300)),
    '"yield spread"': set(range(20100, 21000)),
    "pricing": set(range(20000, 120000)),            # huge generic word
}


def evaluate(query: str) -> set:
    def or_part(part):
        part = part.strip()
        if part.startswith("(") and part.endswith(")"):
            part = part[1:-1]
        hits = set()
        for t in part.split(" OR "):
            hits |= TERM_HITS.get(t.strip(), set())
        return hits
    parts = query.split(" AND ")
    result = or_part(parts[0])
    for p in parts[1:]:
        result &= or_part(p)
    return result


class FakeResp:
    def __init__(self, payload, url):
        self._payload, self.status_code, self.url, self.headers, self.text = payload, 200, url, {}, ""

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.headers, self.calls = {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        q = next(v for k, v in params.items() if k.startswith("search"))
        return FakeResp({"meta": {"count": len(evaluate(q)), "cost": 10, "db_response_time_ms": 5},
                         "results": []}, url)


@pytest.fixture
def cfg():
    from kwpipe.config import load_config
    c = load_config()
    c["openalex"]["pause_s"] = 0
    return c


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")


@pytest.fixture
def keywords_csv(tmp_path):
    rows = [
        "term_id,keyword_term,term_type,group,category,facet,usage_rule,source,status,decided_by,decided_on,notes",
        "K0001,green bond,primary,Green bonds,Instrument,A,,legacy,approved,,,",
        "K0002,climate bond,alternative,Green bonds,Instrument,A,,legacy,approved,,,",
        "K0003,green bonds,alternative,Green bonds,Instrument,A,,legacy,approved,,,",
        "K0004,greenium,primary,Pricing,Outcome,B,,legacy,approved,,,",
        "K0005,yield spread,alternative,Pricing,Outcome,B,,legacy,approved,,,",
        "K0006,pricing,alternative,Pricing,Outcome,B,,legacy,approved,,,",
        "K0007,rejected term,primary,Other,Other,,,legacy,rejected,,,",
    ]
    p = tmp_path / "keywords.csv"
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return p
