"""Stage 5: what each alternative adds beyond its group's primaries.

Per group: count(P) with P = primaries ORed, then count(P OR alt) and count(alt) for each alternative.
Metrics and verdict rules: docs/metrics.md. Thresholds: config/project.yaml.
"""
import argparse

import pandas as pd

from kwpipe.config import load_config
from kwpipe.keywords import groups, load_keywords, validate_keywords
from kwpipe.metrics import variant_gain
from kwpipe.openalex import OpenAlex
from kwpipe.queries import or_query
from kwpipe.runs import finish_run, start_run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keywords", default="data/02_keywords/keywords.csv")
    ap.add_argument("--resume")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir, meta = start_run("variant_gain", cfg, inputs={"keywords": args.keywords},
                              resume=args.resume, params=vars(args))
    kw = load_keywords(args.keywords, quote_phrases=cfg["openalex"]["quote_phrases"])
    checks = validate_keywords(kw, run_dir)
    oa = OpenAlex(cfg, run_dir)

    items, rows, skipped = [], [], []
    for g, prim, alts in groups(kw):
        if prim.empty:
            skipped.append(g)
            continue
        p = or_query(prim["search_term"].tolist())
        items.append((f"P|{g}", p, f"{g} [primaries]"))
        for a in alts.itertuples():
            items.append((f"A|{a.term_id}", a.search_term, a.keyword_term))
            items.append((f"PA|{a.term_id}", or_query(prim["search_term"].tolist() + [a.search_term]),
                          f"{g} [primaries + {a.keyword_term}]"))
            rows.append({"group": g, "primaries": " | ".join(prim["keyword_term"]),
                         "term_id": a.term_id, "keyword_term": a.keyword_term, "search_term": a.search_term})
    if skipped:
        print(f"Groups without a primary term (skipped): {skipped}")

    n, est = oa.count_plan_cost(items)
    if not oa.confirm(n, est, args.yes):
        return
    counts, stop = oa.count_many(items)

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No alternatives to test.")
    df["count_primaries"] = df["group"].map(lambda g: counts.get(f"P|{g}"))
    df["count_alt_alone"] = df["term_id"].map(lambda t: counts.get(f"A|{t}"))
    df["count_primaries_plus_alt"] = df["term_id"].map(lambda t: counts.get(f"PA|{t}"))
    for c in ["count_primaries", "count_alt_alone", "count_primaries_plus_alt"]:
        df[c] = pd.to_numeric(df[c])
    out = variant_gain(df, cfg["thresholds"])
    out["decision"] = ""          # human: keep | drop | promote | move | review
    out["decision_reason"] = ""
    out.to_csv(run_dir / "variant_gain.csv", index=False, encoding="utf-8")

    print(out["verdict"].value_counts().to_string())
    if (~out["consistent"]).any():
        print(f"WARNING: {(~out['consistent']).sum()} rows with inconsistent counts; check those queries.")
    finish_run(run_dir, meta, {"stop_reason": stop, "alternatives": len(out), "skipped_groups": skipped,
                               "verdicts": out["verdict"].value_counts().to_dict(),
                               "thresholds": cfg["thresholds"], "spent_usd": round(oa.spent_usd, 4), "keyword_checks": checks})


if __name__ == "__main__":
    main()
