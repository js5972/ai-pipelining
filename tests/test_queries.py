from kwpipe.queries import chunk_or_queries, format_term, match_type, or_query, query_id


def test_match_type():
    assert match_type("greenium") == "word"
    assert match_type("green bond") == "phrase"
    assert match_type("psoriat*") == "wildcard"


def test_format_term_quotes_phrases_only():
    assert format_term("green  bond") == '"green bond"'
    assert format_term("greenium") == "greenium"
    assert format_term('"green bond"') == '"green bond"'
    assert format_term("green bond", quote_phrases=False) == "green bond"


def test_or_query():
    assert or_query(["a"]) == "a"
    assert or_query(["a", '"b c"']) == '(a OR "b c")'


def test_chunk_or_queries_respects_length():
    terms = [f"term{i}" for i in range(50)]
    chunks = chunk_or_queries(terms, 60)
    assert all(len(c) <= 60 for c in chunks)
    joined = " ".join(chunks)
    assert all(t in joined for t in terms)


def test_query_id_is_deterministic_and_order_free():
    assert query_id("works", {"a": 1, "b": 2}) == query_id("/works", {"b": 2, "a": 1})
    assert query_id("works", {"a": 1}) != query_id("works", {"a": 2})
