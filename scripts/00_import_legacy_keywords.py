"""Convert a legacy keyword list into data/02_keywords/keywords.csv format.

Legacy columns: keyword_term, term_type (primary/alternative), primary_group, category,
usage_recommendation. Writes to the run folder; copy to data/02_keywords/keywords.csv after review.
Use --status approved to make the legacy list the baseline for stages 4-7.
"""
import argparse
from pathlib import Path

import pandas as pd

from kwpipe.config import load_config, resolve
from kwpipe.keywords import COLUMNS, quality_issues
from kwpipe.runs import finish_run, now_utc, start_run

MOJIBAKE = r"[─-╿]"   # box-drawing characters: typical of UTF-8 text read as cp437


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="legacy .csv or .xlsx")
    ap.add_argument("--encoding", default="utf-8", help="CSV encoding (try utf-8-sig for Excel exports)")
    ap.add_argument("--status", default="proposed", choices=["proposed", "approved"])
    ap.add_argument("--decided-by", default="")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir, meta = start_run("import_legacy", cfg, inputs={"legacy": args.input}, params=vars(args))

    path = resolve(args.input)
    raw = (pd.read_excel(path, dtype=str) if path.suffix.lower() in (".xlsx", ".xls")
           else pd.read_csv(path, dtype=str, encoding=args.encoding))
    raw = raw.fillna("")

    df = pd.DataFrame({
        "keyword_term": raw["keyword_term"].str.strip(),
        "term_type": raw["term_type"].str.strip().str.lower(),
        "group": raw["primary_group"].str.strip(),
        "category": raw["category"].str.strip() if "category" in raw else "",
        "usage_rule": raw["usage_recommendation"].str.strip() if "usage_recommendation" in raw else "",
    })
    df = df[df["keyword_term"] != ""].reset_index(drop=True)
    df.insert(0, "term_id", [f"K{i:04d}" for i in range(1, len(df) + 1)])
    df["facet"] = ""
    df["source"] = "legacy"
    df["status"] = args.status
    df["decided_by"] = args.decided_by if args.status == "approved" else ""
    df["decided_on"] = now_utc()[:10] if args.status == "approved" else ""
    df["notes"] = ""
    df = df[COLUMNS]

    issues = quality_issues(df)
    garbled = df["keyword_term"].str.contains(MOJIBAKE, regex=True)
    if garbled.any():
        print(f"WARNING: {garbled.sum()} terms contain box-drawing characters (likely an encoding error):")
        print(df.loc[garbled, ["term_id", "keyword_term"]].to_string(index=False))
        print("Re-export the source as UTF-8 or re-run with the right --encoding.\n")

    df.to_csv(run_dir / "keywords.csv", index=False, encoding="utf-8")
    df.join(issues).to_csv(run_dir / "keywords_issues.csv", index=False, encoding="utf-8")
    print(issues.sum().to_string())
    print(f"\nReview {Path(run_dir.name) / 'keywords_issues.csv'}, then copy keywords.csv to data/02_keywords/.")
    finish_run(run_dir, meta, {"rows": len(df), "garbled": int(garbled.sum()),
                               "issues": {k: int(v) for k, v in issues.sum().items()}})


if __name__ == "__main__":
    main()
