import pandas as pd

from kwpipe.metrics import reconstruct_abstract, variant_gain

T = {"redundant_share": 0.01, "large_gain_share": 0.10, "mostly_new": 0.5}


def row(p, a, pa):
    return {"count_primaries": p, "count_alt_alone": a, "count_primaries_plus_alt": pa}


def test_worked_example():
    out = variant_gain(pd.DataFrame([row(8000, 900, 8600)]), T).iloc[0]
    assert out["gain"] == 600
    assert out["overlap_with_primaries"] == 300
    assert abs(out["gain_vs_group"] - 0.075) < 1e-9
    assert abs(out["new_share_of_alt"] - 600 / 900) < 1e-9
    assert out["verdict"] == "niche"


def test_verdicts():
    df = pd.DataFrame([
        row(1000, 0, 1000),       # matches nothing
        row(1000, 500, 1005),     # redundant
        row(1000, 400, 1300),     # suspicious: +30%, 75% new
        row(1000, 800, 1200),     # strong synonym: +20%, 25% new
        row(1000, 100, 1030),     # minor variant: +3%, 30% new
        row(0, 100, 100),         # primaries match nothing
    ])
    assert variant_gain(df, T)["verdict"].tolist() == [
        "matches nothing", "redundant", "suspicious", "strong synonym", "minor variant",
        "primaries match nothing"]


def test_inconsistent_counts_flagged():
    out = variant_gain(pd.DataFrame([row(1000, 100, 1200)]), T).iloc[0]
    assert not out["consistent"]


def test_reconstruct_abstract():
    assert reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"
    assert reconstruct_abstract(None) == ""
