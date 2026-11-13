"""Stage 1: extract and clean text from text-based PDFs in data/01_sources/ (no OCR).

Cleaning (kept deliberately simple; see docs/workflow.md):
- joins words hyphenated across line breaks,
- cuts the reference list from a References/Bibliography heading in the second half of the text,
- drops short lines and lines that are mostly digits/symbols (table rows, axis labels, captions).
"""
import argparse
import re

import pandas as pd

from kwpipe.config import load_config, resolve, sha256_file
from kwpipe.runs import finish_run, start_run

REF_HEADING = re.compile(r"^\s*(references|bibliography|works cited|literature cited)\s*$", re.I | re.M)


def clean_text(text: str):
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    cut = False
    matches = [m for m in REF_HEADING.finditer(text) if m.start() > len(text) * 0.5]
    if matches:
        text, cut = text[: matches[-1].start()], True
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if len(s) < 3:
            continue
        letters = sum(ch.isalpha() for ch in s)
        if letters / len(s) < 0.5:
            continue
        kept.append(s)
    return "\n".join(kept), cut


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default="data/01_sources")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    from pypdf import PdfReader   # optional dependency: pip install -e ".[extract]"

    cfg = load_config(args.config)
    pdfs = sorted(resolve(args.sources).glob("*.pdf"))
    run_dir, meta = start_run("parse_sources", cfg, inputs={p.name: p for p in pdfs}, params=vars(args))
    out_dir = run_dir / "texts"
    out_dir.mkdir()

    rows = []
    for i, pdf in enumerate(pdfs, 1):
        doc_id = f"D{i:03d}"
        try:
            reader = PdfReader(pdf)
            raw = "\n".join(page.extract_text() or "" for page in reader.pages)
            text, cut = clean_text(raw)
            (out_dir / f"{doc_id}.txt").write_text(text, encoding="utf-8")
            n_pages, error = len(reader.pages), ""
        except Exception as exc:  # report and continue with the other documents
            text, cut, n_pages, raw, error = "", False, 0, "", str(exc)
        rows.append({"doc_id": doc_id, "file": pdf.name, "sha256": sha256_file(pdf), "n_pages": n_pages,
                     "raw_chars": len(raw), "clean_chars": len(text), "references_cut": cut,
                     "likely_scanned": n_pages > 0 and len(raw) / n_pages < 200, "error": error})

    docs = pd.DataFrame(rows)
    docs.to_csv(run_dir / "documents.csv", index=False)
    print(docs.to_string(index=False))
    finish_run(run_dir, meta, {"documents": len(docs),
                               "likely_scanned": int(docs["likely_scanned"].sum()) if len(docs) else 0,
                               "errors": int((docs["error"] != "").sum()) if len(docs) else 0})


if __name__ == "__main__":
    main()
