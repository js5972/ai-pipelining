"""Stage 3: turn candidates into a review sheet in keyword-table format (status = proposed).

Normalises and de-duplicates candidates (lowercase, simple plural folding), marks terms already in
data/02_keywords/keywords.csv, and leaves group/term_type for the agent to propose and humans to approve.
Approved rows are then copied by a human into data/02_keywords/keywords.csv (gate G2).
"""
import argparse

import pandas as pd

from kwpipe.config import load_config, resolve
from kwpipe.keywords import COLUMNS, load_keywords
from kwpipe.runs import finish_run, start_run


def fold(term: str) -> str:
    """Very simple plural folding for de-duplication: 'green bonds' -> 'green bond'."""
    words = term.lower().split()
    if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", required=True, help="runs/<extract_run_id>/candidates.csv")
    ap.add_argument("--keywords", default="data/02_keywords/keywords.csv")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    run_dir, meta = start_run("review_sheet", cfg, inputs={"candidates": args.candidates,
                                                           "keywords": args.keywords}, params=vars(args))
    cand = pd.read_csv(resolve(args.candidates), encoding="utf-8")
    cand["fold"] = cand["candidate"].map(fold)
    cand = cand.sort_values("doc_freq", ascending=False).drop_duplicates("fold")

    existing = load_keywords(args.keywords, statuses=None)
    known = set(existing["keyword_term"].map(fold))
    next_id = len(existing) + 1

    sheet = pd.DataFrame({c: "" for c in COLUMNS}, index=range(len(cand)))
    sheet["term_id"] = [f"K{next_id + i:04d}" for i in range(len(cand))]
    sheet["keyword_term"] = cand["candidate"].values
    sheet["source"] = cand["sources"].values
    sheet["status"] = "proposed"
    evidence = cand[[c for c in ["freq_total", "doc_freq", "keybert_docs", "keybert_mean_score"] if c in cand]]
    sheet = pd.concat([sheet, evidence.reset_index(drop=True)], axis=1)
    sheet["already_in_keywords"] = cand["fold"].isin(known).values
    sheet.to_csv(run_dir / "review_sheet.csv", index=False, encoding="utf-8")

    finish_run(run_dir, meta, {"candidates": len(cand), "already_in_keywords": int(sheet["already_in_keywords"].sum())})


if __name__ == "__main__":
    main()
