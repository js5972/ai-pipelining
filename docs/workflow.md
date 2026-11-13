# Workflow

Two phases: **keyword extraction** (build an approved keyword table) and **data retrieval** (validate it against OpenAlex, freeze a query, download). A short **scope** stage comes first because both phases depend on it.

```
 0 Scope ──G1──► 1 Parse ► 2 Extract ► 3 Review ──G2──► 4 Counts ► 5 Variant gain ► 6 Unions ► 7 Relevance ──G3──► 8 Retrieve ──G4
                                          ▲                                                        │
                                          └──────────── decisions back into keywords.csv ◄─────────┘
```

Every stage says: what goes in, what comes out, what an agent does, what a human does.

---

## Stage 0 — Scope (manual) · Gate G1

**Why first:** without a written topic definition, nobody (human or agent) can judge whether a keyword or a paper is relevant, and relevance checks later become arbitrary.

- Write `data/00_scope/scope.md`: one-sentence topic, inclusion and exclusion criteria, draft concepts (future facets), time window, document types.
- List seed papers in `data/00_scope/seeds.csv` and give each a `role`:
  - `extraction` — may be used as source text for keyword extraction;
  - `evaluation` — **held out**: never used to build keywords, only to measure recall in stage 7.

  Holding out evaluation seeds avoids circularity: keywords extracted from a paper will always find that paper.
- **Agent:** proposes the scope draft and candidate seeds (e.g. via the OpenAlex connector).
- **Human (G1):** approves scope and seed roles.

## Stage 1 — Parse sources · `01_parse_sources.py`

- **In:** PDFs in `data/01_sources/` (reports, academic papers). Text-based PDFs only; no OCR.
- **Does:** extracts text per document, joins hyphenated line breaks, removes the reference list (from a "References"/"Bibliography" heading in the second half of the document), drops lines that look like table rows or captions (mostly digits/symbols, very short).
- **Out:** `runs/<id>/texts/<doc>.txt`, `documents.csv` (hash, pages, characters, flags such as `likely_scanned`).
- **Human:** skim `documents.csv` for failed or scanned documents.

## Stage 2 — Extract candidates · `02_extract_candidates.py`

One step with two independent sources, so each candidate keeps its provenance:

- **Frequency:** 1–3-word n-grams, English stop words removed, counted per document; kept if they appear in at least `min_doc_freq` documents.
- **Semantic (KeyBERT):** KeyBERT embeds the text and candidates itself, so there is no separate embedding step. Long documents are split into chunks first, because embedding models truncate long input (a 40-page report would otherwise be judged on its first page).
- **Out:** `candidates.csv` with `freq_total`, `doc_freq`, `keybert_docs`, `keybert_mean_score`, `sources`.
- Optional third source (not scripted yet): OpenAlex's own keyword vocabulary via the connector (`find_keywords`) or `/text/keywords` ($0.01 per call).

## Stage 3 — Review sheet · `03_review_sheet.py` · Gate G2

- Normalises and de-duplicates candidates, marks those already in `keywords.csv`, and writes `review_sheet.csv` in the keyword-table format with `status = proposed`.
- **Agent:** proposes `group`, `term_type`, `facet` and **alternatives** (synonyms, spelling variants, acronyms) for each kept candidate, in clearly marked columns, with `source = agent`.
- **Human / expert colleagues (G2):** set `status` to `approved`, `rejected` or `parked`; fix groups; save approved rows into `data/02_keywords/keywords.csv`.

Compared with the original sketch: *gap identification* moved to stage 7 (gaps are only measurable against OpenAlex, as missed seed papers), and *alternative generation* moved before validation, because stage 5 is what tests whether alternatives earn their place.

## Stage 4 — Term counts · `04_term_counts.py`

- One count-only request per approved term (~$0.001 each).
- **Out:** `term_counts.csv` with flags `zero`, `large`, `syntax_watch`.
- **Read it for:** encoding errors, terms that match nothing, terms that are huge (generic words, or phrases not quoted).

## Stage 5 — Variant gain · `05_variant_gain.py`

- Per group: count the primaries ORed together (P), then P OR each alternative.
- **Out:** `variant_gain.csv` with `gain`, `gain_vs_group`, `new_share_of_alt` and a `verdict` (see `docs/metrics.md`).
- **Decisions:** drop terms that match nothing; redundant terms are optional; `suspicious` terms go to stage 7 sampling; strong synonyms may become primaries; terms that mostly find *other* papers may belong to a different group or facet.

## Stage 6 — Group unions · `06_group_unions.py`

- Counts each group with all its terms ORed, the full union of all terms (the **baseline corpus size**), and, if the `facet` column is filled, the facet query (OR within a facet, AND between facets).
- Splits the full union into chunks if the query is too long for one URL.
- **Out:** `group_unions.csv`, `query_draft.yaml` (a ready-to-edit candidate for `data/04_query/query.yaml`).

## Stage 7 — Relevance · `07_relevance.py`

- **Seed recall:** which seeds each query finds; reported separately for `extraction` and `evaluation` seeds. Missed evaluation seeds = **gaps**: read their titles/abstracts for missing vocabulary.
- **Samples:** a seeded random sample of each query's results (not the top hits) written as a labelling sheet.
- **Human:** labels samples (`label_human`: relevant / not_relevant / unsure); labels accumulate in `data/03_labels/labels.csv`.
- **Agent (optional):** pre-labels in `label_agent` with a reason; the agreement rate with human labels decides whether agent labels can be trusted at scale.

## Gate G3 — Freeze the query

Copy the chosen query from `query_draft.yaml` into `data/04_query/query.yaml`, fill in `approved_by`, `approved_on`, `description`, and set `approved: true`. The settings in that file (corpus, search scope, quoting) are what retrieval uses, so the query is self-contained.

## Stage 8 — Retrieve · `08_retrieve.py` · Gate G4

- **Phase 1:** cursor-page each query with `select=id` → `ids.txt` (de-duplicated across chunks). This ID list is the frozen corpus definition.
- **Phase 2:** fetch full records 100 IDs at a time with the `openalex:` filter (list price) → `records.jsonl.gz`.
- Both phases checkpoint and resume (`--resume <run_id>`).
- **Checks:** IDs vs. reported count, records vs. IDs, missing IDs (merged/deleted works), field completeness.
- **Human (G4):** accepts the corpus and records it in `docs/decisions.md`.

---

## Reproducibility checklist

- [ ] Config, keywords and query files committed; run metadata records their hashes and the git commit.
- [ ] Settings changes recorded in `docs/decisions.md`.
- [ ] Each benchmark run done within one day (OpenAlex data drifts).
- [ ] Final ID list kept with the retrieval run; record date noted.
- [ ] Random samples use the fixed seed from `config/project.yaml`.
