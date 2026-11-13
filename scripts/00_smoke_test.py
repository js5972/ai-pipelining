"""Check the API, key and parameters work: one count, a small page, a seeded sample twice.

Run this first in any new environment, and use its output to set openalex.reported_cost_unit.
Cost: 4 search requests (< $0.01).
"""
import argparse
import json

from kwpipe.config import load_config
from kwpipe.openalex import OpenAlex
from kwpipe.queries import format_term
from kwpipe.runs import finish_run, start_run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--term", required=True, help='e.g. "green bond"')
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir, meta = start_run("smoke_test", cfg, params=vars(args))
    oa = OpenAlex(cfg, run_dir)
    q = format_term(args.term, cfg["openalex"]["quote_phrases"])
    print("Query:", q)

    r1 = oa.get("works", oa.search_params(q, per_page=1), label="count_only", cache=False)
    print("meta:", json.dumps(r1["meta"], indent=2))
    print("Fields in a work record:", sorted(r1["results"][0]) if r1["results"] else "no results")
    print(f"\nmeta.cost = {r1['meta'].get('cost')!r} -> compare with the published search price "
          f"(${cfg['prices_usd']['search']}) to set openalex.reported_cost_unit (credits or usd).")

    r2 = oa.get("works", oa.search_params(q, per_page=5, select="id,display_name,publication_year"),
                label="small_page", cache=False)
    for w in r2["results"]:
        print(" ", w["publication_year"], w["display_name"][:100])

    p = oa.search_params(q, sample=10, seed=cfg["sampling"]["seed"], per_page=10, select="id")
    a = [w["id"] for w in oa.get("works", p, label="sample_a", cache=False)["results"]]
    b = [w["id"] for w in oa.get("works", p, label="sample_b", cache=False)["results"]]
    print("\nSeeded sample reproducible:", a == b)

    finish_run(run_dir, meta, {"count": r1["meta"]["count"], "reported_cost": r1["meta"].get("cost"),
                               "sample_reproducible": a == b, "spent_usd": round(oa.spent_usd, 4)})


if __name__ == "__main__":
    main()
