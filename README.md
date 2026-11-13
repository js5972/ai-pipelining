# OpenAlex keyword pipeline

A reproducible, human-centred pipeline for:

1. **Building a keyword list** for a research topic, from source documents (reports, papers) and expert review.
2. **Validating that list** against OpenAlex with cheap count queries.
3. **Retrieving the metadata** of all matching works from the OpenAlex API.

Agents (Codex, Claude, …) can run and extend the pipeline. **Humans approve every decision that changes what gets retrieved.** Everything an agent or a person decides is written to a file in this repo.

## Design principles

- **Plain files, plain scripts.** CSV, YAML, JSONL. One numbered script per stage, run in order. No database, no orchestration framework.
- **Approved inputs live in `data/` (versioned). Generated outputs live in `runs/` (not versioned).**
- **Every run is traceable.** Each script creates `runs/<run_id>/` with `run_metadata.json` (git commit, config hash, input file hashes, package versions) and, for API stages, a `request_log.jsonl` with every request, its cost and its timing.
- **Human gates are enforced in code.** The retrieval script refuses to run unless `data/04_query/query.yaml` says `approved: true`.
- **Budget limits are enforced in code**, not left to an agent's discretion.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # core: API stages
pip install -e ".[extract]"        # optional: keyword extraction from PDFs (pypdf, scikit-learn, KeyBERT)

cp .env.example .env               # then put your key in .env
export $(grep -v '^#' .env | xargs)

python scripts/00_smoke_test.py --term "green bond"
pytest
```

## Workflow at a glance

| Stage | Script | Reads | Writes | Human gate |
|---|---|---|---|---|
| 0. Scope | (manual) | — | `data/00_scope/scope.md`, `seeds.csv` | **G1: scope approved** |
| 1. Parse sources | `01_parse_sources.py` | `data/01_sources/*.pdf` | `runs/…/texts/` | — |
| 2. Extract candidates | `02_extract_candidates.py` | parsed texts | `runs/…/candidates.csv` | — |
| 3. Review sheet | `03_review_sheet.py` | candidates | `runs/…/review_sheet.csv` | **G2: keyword list approved** → `data/02_keywords/keywords.csv` |
| 4. Term counts | `04_term_counts.py` | keywords | `runs/…/term_counts.csv` | — |
| 5. Variant gain | `05_variant_gain.py` | keywords | `runs/…/variant_gain.csv` | decisions back into keywords |
| 6. Group unions | `06_group_unions.py` | keywords | `runs/…/group_unions.csv`, `query_draft.yaml` | — |
| 7. Relevance | `07_relevance.py` | query, seeds | `runs/…/seed_recall.csv`, `sample_*.csv` | labels → `data/03_labels/labels.csv` |
| 8. Retrieve | `08_retrieve.py` | `data/04_query/query.yaml` | `runs/…/ids.txt`, `records.jsonl.gz` | **G3: query approved** (required) |

Stages 4–7 form a loop: results feed decisions back into `keywords.csv` until the query is good enough to freeze.

Full details: [`docs/workflow.md`](docs/workflow.md).

## Repository map

```
AGENTS.md                 rules for coding agents (read first)
config/project.yaml       all settings, thresholds and budget, in one place
data/                     approved inputs and human decisions (versioned)
  00_scope/               topic definition and seed papers
  01_sources/             source documents for extraction (PDFs not committed)
  02_keywords/            keywords.csv: the approved keyword table
  03_labels/              human relevance labels
  04_query/               query.yaml: the frozen, approved query
docs/                     workflow, decisions log, metric definitions, data contracts, OpenAlex notes, backlog
notebooks/                exploration only; never the source of truth
runs/                     one folder per script run (generated, not versioned)
scripts/                  numbered stage scripts
src/kwpipe/               small shared library (config, runs, OpenAlex client, queries, keywords, metrics)
tests/                    unit tests for the library
```

## Starting from an existing keyword list

```bash
python scripts/00_import_legacy_keywords.py --input path/to/old_list.xlsx --status approved
```

This maps the legacy columns (`keyword_term`, `term_type`, `primary_group`, `category`, `usage_recommendation`) to the schema in [`docs/data_contracts.md`](docs/data_contracts.md) and flags encoding problems. Importing with `--status approved` makes the old list usable as the **baseline** for stages 4–7.
