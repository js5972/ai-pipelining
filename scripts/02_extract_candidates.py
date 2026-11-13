"""Stage 2: candidate keywords from parsed texts, by frequency and (optionally) by KeyBERT.

Input: --texts runs/<parse_run_id>/texts. Each candidate keeps its provenance (which method found it).
KeyBERT runs per chunk of `extraction.chunk_words` words, because embedding models truncate long input.
"""
import argparse
from collections import defaultdict

import pandas as pd

from kwpipe.config import load_config, resolve
from kwpipe.runs import finish_run, start_run


def normalise(term: str) -> str:
    return " ".join(term.lower().split())


def chunks(text: str, size: int):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i + size])


def frequency_candidates(docs: dict, x: dict) -> pd.DataFrame:
    from sklearn.feature_extraction.text import CountVectorizer
    vec = CountVectorizer(ngram_range=(x["ngram_min"], x["ngram_max"]), stop_words="english",
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]+\b", lowercase=True)
    m = vec.fit_transform(docs.values())
    terms = vec.get_feature_names_out()
    total = m.sum(axis=0).A1
    doc_freq = (m > 0).sum(axis=0).A1
    df = pd.DataFrame({"candidate": terms, "freq_total": total, "doc_freq": doc_freq})
    df = df[df["doc_freq"] >= min(x["min_doc_freq"], len(docs))]
    return df.sort_values(["doc_freq", "freq_total"], ascending=False).head(x["top_n_frequency"])


def keybert_candidates(docs: dict, x: dict) -> pd.DataFrame:
    from keybert import KeyBERT
    kb = KeyBERT(model=x["keybert_model"])
    hits = defaultdict(lambda: {"docs": set(), "scores": []})
    for doc_id, text in docs.items():
        for chunk in chunks(text, x["chunk_words"]):
            for term, score in kb.extract_keywords(
                    chunk, keyphrase_ngram_range=(x["ngram_min"], x["ngram_max"]), stop_words="english",
                    use_mmr=True, diversity=x["keybert_diversity"], top_n=x["keybert_top_n_per_chunk"]):
                hits[normalise(term)]["docs"].add(doc_id)
                hits[normalise(term)]["scores"].append(score)
    return pd.DataFrame([{"candidate": t, "keybert_docs": len(h["docs"]),
                          "keybert_mean_score": sum(h["scores"]) / len(h["scores"])} for t, h in hits.items()])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--texts", required=True, help="runs/<parse_run_id>/texts")
    ap.add_argument("--no-semantic", action="store_true", help="skip KeyBERT")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    x = cfg["extraction"]
    files = sorted(resolve(args.texts).glob("*.txt"))
    run_dir, meta = start_run("extract_candidates", cfg, inputs={f.name: f for f in files}, params=vars(args))
    docs = {f.stem: f.read_text(encoding="utf-8") for f in files}
    if not docs:
        raise SystemExit(f"No .txt files in {args.texts}")

    freq = frequency_candidates(docs, x)
    freq["candidate"] = freq["candidate"].map(normalise)
    out = freq
    if not args.no_semantic:
        sem = keybert_candidates(docs, x)
        out = freq.merge(sem, on="candidate", how="outer") if len(sem) else freq
    for c in ["freq_total", "doc_freq", "keybert_docs"]:
        if c in out:
            out[c] = out[c].fillna(0).astype(int)
    out["sources"] = out.apply(lambda r: "|".join(
        s for s, ok in [("frequency", r.get("freq_total", 0) > 0), ("keybert", r.get("keybert_docs", 0) > 0)] if ok),
        axis=1)
    out = out.sort_values(["sources", "doc_freq"], ascending=[True, False])
    out.to_csv(run_dir / "candidates.csv", index=False, encoding="utf-8")
    finish_run(run_dir, meta, {"documents": len(docs), "candidates": len(out),
                               "by_source": out["sources"].value_counts().to_dict()})


if __name__ == "__main__":
    main()
