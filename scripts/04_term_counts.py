"""Stage 4: one count-only request per approved keyword (~$0.001 each)."""
import argparse

from kwpipe.config import load_config
from kwpipe.keywords import load_keywords, quality_issues, validate_keywords
from kwpipe.openalex import OpenAlex
from kwpipe.runs import finish_run, start_run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keywords", default="data/02_keywords/keywords.csv")
    ap.add_argument("--resume", help="run_id to resume")
    ap.add_argument("--yes", action="store_true", help="don't ask before spending")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir, meta = start_run("term_counts", cfg, inputs={"keywords": args.keywords},
                              resume=args.resume, params=vars(args))
    kw = load_keywords(args.keywords, quote_phrases=cfg["openalex"]["quote_phrases"])
    checks = validate_keywords(kw, run_dir)
    oa = OpenAlex(cfg, run_dir)

    items = [(r.term_id, r.search_term, r.keyword_term) for r in kw.itertuples()]
    n, est = oa.count_plan_cost(items)
    if not oa.confirm(n, est, args.yes):
        return
    counts, stop = oa.count_many(items)

    issues = quality_issues(kw)
    out = kw[["term_id", "keyword_term", "search_term", "term_type", "group", "category", "match_type"]].copy()
    out["count"] = out["term_id"].map(counts)
    out["flag_zero"] = out["count"].eq(0)
    out["flag_large"] = out["count"].gt(cfg["thresholds"]["large_count"])
    out["flag_syntax"] = issues[["boolean_chars", "boolean_words", "short_wildcard", "non_ascii"]].any(axis=1)
    out["flag_not_run"] = out["count"].isna()
    out.to_csv(run_dir / "term_counts.csv", index=False, encoding="utf-8")

    print(out.sort_values("count", ascending=False).head(15).to_string(index=False))
    finish_run(run_dir, meta, {"stop_reason": stop, "terms": len(out), "keyword_checks": checks,
                               **{c: int(out[c].sum()) for c in ["flag_zero", "flag_large", "flag_syntax", "flag_not_run"]},
                               "spent_usd": round(oa.spent_usd, 4)})


if __name__ == "__main__":
    main()
