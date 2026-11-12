# ai-pipelining

A first reproducible literature-search pilot, based on the supplied design conversation. Python 3.12+, standard library only; no installation or external model needed for offline execution.

```sh
cd /workspace/ai-pipelining
python -m unittest discover -s tests -v
python -m examples.offline_demo
python -m pipeline --help
```

The demo uses **synthetic documents and API responses**, not real papers or retrieval-quality evidence. Run it again to exercise archive reuse. Delete only `.runs/offline-demo` to generate a new synthetic run.

## Workflow

1. Supply a JSON array of documents with unique `id`, `title`, and `abstract` fields (see `examples/documents.json`). Preserve original sources separately. This pilot accepts structured text, not PDFs.
2. Generate proposals:
   `python -m pipeline extract examples/documents.json .runs/candidates.json`
3. Review the registry. For chosen terms, set `status` to `approved`, assign `concept_group`, and record `decision` with `reviewer` and `rationale`. Evidence is retained from the seed text. Unapproved terms never compile. `examples/registry.json` is a reviewed synthetic fixture, not a scientific vocabulary.
4. Write a query specification with `strategy` (`concept_groups` or exploratory `all_or`), required `groups`, optional `max_requests` (default 100), and optional `filters`: `from_publication_date`, `to_publication_date`, `language`, `type`.
5. Compile:
   `python -m pipeline compile examples/registry.json examples/query-spec.json .runs/plan.json`
6. Retrieve a frozen plan into a **new run directory**:
   `python -m pipeline retrieve .runs/plan.json .runs/live-001`
   Set `OPENALEX_API_KEY` securely in the environment if required by the service. The client sends it only to `https://api.openalex.org`; it is excluded from archived parameters and HTTP error messages. Live access requires this domain in environment settings.
7. Replay without network access:
   `python -m pipeline replay .runs/live-001`
8. Evaluate with:
   `python -m pipeline evaluate .runs/live-001/corpus.json benchmark.json .runs/metrics.json`
   Benchmark rows require `id`, `relevant` (boolean), `eligible` (confirmed present/in scope in OpenAlex), and `split` (`seed` or `held_out`). Mark manually sampled/labelled rows `sampled: true` for precision. Seeds and ineligible papers are excluded from held-out recall. Sampling and eligibility verification are currently manual; precision is meaningful only for a properly constructed sample.

## Reproducibility contract

Candidate extraction normalizes Unicode and case, extracts sentence-bounded 1–3-word phrases from title/abstract, excludes a fixed stopword set, scores with length-adjusted TF-IDF, and breaks score ties lexically. It is an intentionally modest baseline. Source-document hashes, passages, and algorithm settings are stored. It does not prove semantic usefulness.

The compiler enumerates one quoted phrase per concept group, joined with `AND`, and unions responses across combinations. This preserves the intended group logic rather than unioning independent group searches. It rejects unsupported phrase characters and excessive expansion. **Live OpenAlex Boolean/phrase behavior has not been validated in this environment**; treat live retrieval as experimental until representative probes and benchmark review pass.

Every run saves its exact plan, hashes, Python/code versions, Git commit and dirty state, credential-free request parameters, timestamps, raw pages, cursors, completion flag, and deduplicated corpus with query membership. Commit reviewed source/configuration before research runs: a dirty Git flag does not preserve uncommitted source. The client retries selected HTTP errors up to four attempts and checkpoints each successful page. Resume using the same directory/plan; use a new directory for refreshes. Interrupted pages may be fetched again. Replay verifies plan/page checksums and rejects incomplete runs. Retain archives: a publication-date filter does not freeze OpenAlex data.

## Scope and next experiments

Implemented: deterministic extraction, evidence registry, approval gate, concept/all-OR compilation, cursor retrieval/resume, raw archives, replay, deduplication, and basic held-out metrics; tests use a simulated API.

Still needed for the research milestone: your research question and seed/held-out papers; PDF/XML parsing and quality flags; stronger schema/provenance validation; pinned semantic extraction and rank fusion; fixed-seed sampling and marginal-yield/subtopic analysis; live query semantics, API limits, authentication and completeness/count checks; source snapshots and release packaging. No claims of retrieval accuracy follow from fixture tests.

Agents should propose registry changes for review, then invoke the same versioned CLI. They should not silently approve terms or modify a frozen run.
