"""Load and check the keyword table (docs/data_contracts.md)."""
import pandas as pd

from .config import resolve
from .queries import BOOLEAN_CHARS, format_term, match_type

COLUMNS = ["term_id", "keyword_term", "term_type", "group", "category", "facet", "usage_rule",
           "source", "status", "decided_by", "decided_on", "notes"]
REQUIRED = ["term_id", "keyword_term", "term_type", "group", "status"]

STATUSES = ["proposed", "approved", "rejected", "parked"]

# Problems that make queries wrong: stop before spending anything
ERRORS = ["duplicate_term_id", "bad_term_type", "missing_group", "boolean_words", "short_wildcard"]
# Problems worth a look but not blocking
WARNINGS = ["non_ascii", "boolean_chars", "duplicate_in_group", "duplicate_across_groups",
            "group_without_primary", "single_term_group", "approved_without_decider"]

def load_keywords(path, statuses=("approved",), quote_phrases=True) -> pd.DataFrame:
    """Read keywords.csv (UTF-8), normalise text, keep rows with the given statuses,
    and add match_type and search_term columns."""
    df = pd.read_csv(resolve(path), dtype=str, encoding="utf-8", keep_default_na=False)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Keyword table is missing columns: {missing}")
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    df["keyword_term"] = df["keyword_term"].str.split().str.join(" ")
    df["term_type"] = df["term_type"].str.lower()
    df["status"] = df["status"].str.lower()
    if statuses:
        df = df[df["status"].isin(statuses)]
    df = df[df["keyword_term"] != ""].reset_index(drop=True)
    df["match_type"] = df["keyword_term"].map(match_type)
    df["search_term"] = df["keyword_term"].map(lambda t: format_term(t, quote_phrases))
    return df


def quality_issues(df: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per possible problem, aligned with df's rows."""
    term = df["keyword_term"].fillna("")
    low = term.str.lower()
    same_group = df.assign(_l=low).duplicated(["group", "_l"], keep=False)
    return pd.DataFrame({
        "duplicate_term_id": df["term_id"].duplicated(keep=False),
        "bad_term_type": ~df["term_type"].isin(["primary", "alternative"]),
        "missing_group": df["group"].eq(""),
        "duplicate_in_group": same_group,
        "duplicate_across_groups": low.duplicated(keep=False) & ~same_group,
        "non_ascii": term.str.contains(r"[^\x00-\x7F]", regex=True),
        "boolean_chars": term.map(lambda t: any(ch in t for ch in BOOLEAN_CHARS)),
        "boolean_words": term.str.contains(r"\b(?:AND|OR|NOT)\b", regex=True),
        "short_wildcard": term.str.contains(r"(?:^|\s)\S{0,2}\*", regex=True),
    }, index=df.index)


def groups(df: pd.DataFrame):
    """Yield (group, primaries_df, alternatives_df)."""
    for g, part in df.groupby("group", sort=True):
        yield g, part[part["term_type"] == "primary"], part[part["term_type"] == "alternative"]



class KeywordTableError(ValueError):
    pass


def structure_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Group-level checks, as one boolean column per problem aligned with df's rows."""
    by_group = df.groupby("group")
    has_primary = by_group["term_type"].transform(lambda s: (s == "primary").any())
    size = by_group["term_id"].transform("size")
    return pd.DataFrame({
        "group_without_primary": ~has_primary & df["group"].ne(""),
        "single_term_group": size.eq(1),
        "approved_without_decider": df["status"].eq("approved") & df["decided_by"].eq(""),
    }, index=df.index)


def check_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """All checks: row-level (quality_issues) and group-level (structure_issues)."""
    return quality_issues(df).join(structure_issues(df))


def validate_keywords(df: pd.DataFrame, run_dir=None) -> dict:
    """Run all checks. Raise KeywordTableError on errors; print warnings.
    If run_dir is given, write keyword_checks.csv there. Returns counts per check."""
    issues = check_keywords(df)
    counts = {c: int(issues[c].sum()) for c in issues.columns}
    if run_dir is not None:
        df.join(issues).to_csv(run_dir / "keyword_checks.csv", index=False, encoding="utf-8")

    bad = issues[ERRORS].any(axis=1)
    if bad.any():
        rows = df.loc[bad, ["term_id", "keyword_term", "term_type", "group"]].join(issues.loc[bad, ERRORS])
        raise KeywordTableError(f"{bad.sum()} rows have blocking problems:\n{rows.to_string(index=False)}")

    for c in WARNINGS:
        if counts[c]:
            print(f"WARNING {c}: {counts[c]} rows (see keyword_checks.csv)")
    return counts
