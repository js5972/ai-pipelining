"""Building search strings and stable query IDs."""
import hashlib
import json

BOOLEAN_CHARS = '()"|:'


def match_type(term: str) -> str:
    """word (stemmed by OpenAlex), phrase (several words) or wildcard (contains *)."""
    term = term.strip()
    if "*" in term:
        return "wildcard"
    if len(term.split()) > 1:
        return "phrase"
    return "word"


def format_term(term: str, quote_phrases: bool = True) -> str:
    """How a keyword is written into a search: phrases quoted if the setting says so."""
    term = " ".join(term.split())
    already_quoted = term.startswith('"') and term.endswith('"')
    if quote_phrases and match_type(term) == "phrase" and not already_quoted:
        return f'"{term}"'
    return term


def or_query(terms) -> str:
    terms = [t for t in terms if isinstance(t, str) and t.strip()]
    if not terms:
        raise ValueError("or_query needs at least one term")
    return terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"


def and_query(parts) -> str:
    parts = [p for p in parts if isinstance(p, str) and p.strip()]
    if not parts:
        raise ValueError("and_query needs at least one part")
    return parts[0] if len(parts) == 1 else " AND ".join(parts)


def not_query(include: str, exclude: str) -> str:
    return f"{include} NOT {exclude}"


def chunk_or_queries(terms, max_chars: int):
    """Split terms into several OR-queries, each at most max_chars long."""
    chunks, current = [], []
    for t in terms:
        if current and len(or_query(current + [t])) > max_chars:
            chunks.append(or_query(current))
            current = []
        current.append(t)
    if current:
        chunks.append(or_query(current))
    return chunks


def query_id(endpoint: str, params: dict) -> str:
    """Deterministic ID: the same request always gets the same ID (used for caching/resume)."""
    key = json.dumps({"endpoint": endpoint.strip("/"), "params": params}, sort_keys=True)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
