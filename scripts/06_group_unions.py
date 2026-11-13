"""Stage 6: size of each group (all terms ORed), the full union (baseline corpus size) and, if the
`facet` column is filled, the facet query (OR within a facet, AND between facets).
Writes query_draft.yaml as a starting point for data/04_query/query.yaml.
"""
import argparse

import pandas as pd
import yaml

from kwpipe.config import load_config, resolve, sha256_file
from kwpipe.keywords import load_keywords, validate_keywords
from kwpipe.openalex import OpenAlex
from kwpipe.queries import and_query, chunk_or_queries, or_query
from kwpipe.runs import finish_run, start_run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keywords", default="data/02_keywords/keywords.csv")
    ap.add_argument("--term-counts", help="runs/<term_counts_run>/term_counts.csv, to add overlap ratios")
    ap.add_argument("--resume")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    max_chars = cfg["openalex"]["max_query_chars"]
    run_dir, meta = start_run("group_unions", cfg, inputs={"keywords": args.keywords},
                              resume=args.resume, params=vars(args))
    kw = load_keywords(args.keywords, quote_phrases=cfg["openalex"]["quote_phrases"])
    checks = validate_keywords(kw, run_dir)
    oa = OpenAlex(cfg, run_dir)

    items = []
    group_queries = {g: or_query(part["search_term"].tolist()) for g, part in kw.groupby("group")}
    long_groups = [g for g, q in group_queries.items() if len(q) > max_chars]
    for g, q in group_queries.items():
        if g not in long_groups:
            items.append((f"G|{g}", q, f"group {g}"))

    union_chunks = chunk_or_queries(kw["search_term"].tolist(), max_chars)
    if len(union_chunks) == 1:
        items.append(("UNION", union_chunks[0], "full union"))
    else:
        print(f"Full union is too long for one request: split into {len(union_chunks)} chunks. "
              "Chunk counts can't be summed; the de-duplicated size comes from retrieval phase 1.")
        items += [(f"UNION|{i}", q, f"union chunk {i}") for i, q in enumerate(union_chunks, 1)]

    facet_query = None
    facets = kw[kw["facet"] != ""]
    if not facets.empty:
        facet_query = and_query([or_query(p["search_term"].tolist()) for _, p in facets.groupby("facet")])
        if len(facet_query) <= max_chars:
            items.append(("FACET", facet_query, "facet query"))

    n, est = oa.count_plan_cost(items)
    if not oa.confirm(n, est, args.yes):
        return
    counts, stop = oa.count_many(items)

    out = (kw.groupby(["category", "group"], dropna=False).size().rename("n_terms").reset_index())
    out["union_count"] = out["group"].map(lambda g: counts.get(f"G|{g}"))
    out["too_long"] = out["group"].isin(long_groups)
    if args.term_counts:
        tc = pd.read_csv(resolve(args.term_counts))
        out = out.merge(tc.groupby("group")["count"].sum().rename("sum_term_counts"), on="group", how="left")
        out["overlap_ratio"] = out["sum_term_counts"] / out["union_count"]
    out.to_csv(run_dir / "group_unions.csv", index=False, encoding="utf-8")

    draft = {
        "approved": False, "approved_by": "", "approved_on": "",
        "description": "DRAFT from 06_group_unions: all approved terms ORed (baseline)",
        "keywords_file": args.keywords, "keywords_sha256": sha256_file(args.keywords),
        "settings": {"corpus": cfg["openalex"]["corpus"], "search_param": cfg["openalex"]["search_param"]},
        "queries": union_chunks,
    }
    if facet_query:
        draft["alternative_facet_query"] = facet_query
    (run_dir / "query_draft.yaml").write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True),
                                              encoding="utf-8")

    summary = {"stop_reason": stop, "groups": len(out), "groups_too_long": long_groups,
               "union_chunks": len(union_chunks), "full_union_count": counts.get("UNION"),
               "facet_query_count": counts.get("FACET"), "spent_usd": round(oa.spent_usd, 4), "keyword_checks": checks}
    print(out.sort_values("union_count", ascending=False).to_string(index=False))
    finish_run(run_dir, meta, summary)


if __name__ == "__main__":
    main()
