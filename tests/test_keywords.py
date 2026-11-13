import pandas as pd
import pytest
from kwpipe.keywords import KeywordTableError, load_keywords, structure_issues, validate_keywords, quality_issues


def test_load_filters_and_quotes(keywords_csv):
    kw = load_keywords(keywords_csv)
    assert "rejected term" not in kw["keyword_term"].tolist()
    assert kw.set_index("term_id").loc["K0001", "search_term"] == '"green bond"'
    assert kw.set_index("term_id").loc["K0004", "search_term"] == "greenium"


def test_quality_issues_flags_encoding_and_duplicates():
    df = pd.DataFrame({"term_id": ["K1", "K2", "K3"], "keyword_term": ["╬╡ risk", "spread", "Spread"],
                       "term_type": ["primary", "primary", "alt"], "group": ["G", "H", "H"]})
    issues = quality_issues(df)
    assert issues.loc[0, "non_ascii"]
    assert issues.loc[1, "duplicate_in_group"] and issues.loc[2, "duplicate_in_group"]
    assert issues.loc[2, "bad_term_type"]

def test_structure_flags_group_without_primary(keywords_csv):
    kw = load_keywords(keywords_csv)
    kw.loc[kw.term_id == "K0004", "term_type"] = "alternative"     # Pricing loses its only primary
    s = structure_issues(kw)
    assert s.loc[kw.group == "Pricing", "group_without_primary"].all()
    assert not s.loc[kw.group == "Green bonds", "group_without_primary"].any()


def test_validate_blocks_errors(keywords_csv):
    kw = load_keywords(keywords_csv)
    kw.loc[0, "term_type"] = "main"
    with pytest.raises(KeywordTableError):
        validate_keywords(kw)


def test_validate_writes_checks(keywords_csv, tmp_path):
    counts = validate_keywords(load_keywords(keywords_csv), tmp_path)
    assert (tmp_path / "keyword_checks.csv").exists()
    assert counts["group_without_primary"] == 0