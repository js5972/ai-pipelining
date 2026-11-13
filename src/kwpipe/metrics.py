"""Variant-gain metrics and verdicts (docs/metrics.md)."""
import pandas as pd


def variant_gain(df: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    """df needs count_primaries, count_alt_alone, count_primaries_plus_alt.
    Adds gain, overlap_with_primaries, gain_vs_group, new_share_of_alt, verdict, consistent."""
    out = df.copy()
    out["gain"] = out["count_primaries_plus_alt"] - out["count_primaries"]
    out["overlap_with_primaries"] = out["count_alt_alone"] - out["gain"]
    out["gain_vs_group"] = out["gain"] / out["count_primaries"].where(out["count_primaries"] > 0)
    out["new_share_of_alt"] = out["gain"] / out["count_alt_alone"].where(out["count_alt_alone"] > 0)
    # Sanity: 0 <= gain <= count_alt_alone; otherwise the counts are not comparable
    out["consistent"] = (out["gain"] >= 0) & (out["gain"] <= out["count_alt_alone"])
    out["verdict"] = out.apply(lambda r: classify(r, thresholds), axis=1)
    return out


def classify(r, t: dict) -> str:
    if pd.isna(r["count_alt_alone"]) or pd.isna(r["count_primaries_plus_alt"]):
        return "not run"
    if r["count_alt_alone"] == 0:
        return "matches nothing"
    if pd.isna(r["gain_vs_group"]):          # group's primaries match nothing
        return "primaries match nothing"
    if r["gain_vs_group"] < t["redundant_share"]:
        return "redundant"
    mostly_new = r["new_share_of_alt"] >= t["mostly_new"]
    if r["gain_vs_group"] >= t["large_gain_share"]:
        return "suspicious" if mostly_new else "strong synonym"
    return "niche" if mostly_new else "minor variant"


def reconstruct_abstract(inverted_index) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return ""
    positions = [(pos, word) for word, poss in inverted_index.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))
