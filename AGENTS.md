# Instructions for coding agents

Read this file, then `README.md`, `docs/workflow.md` and `docs/decisions.md` before doing anything.

## What this project is

A pipeline that turns a research topic into an approved keyword list and then into a reproducible download of OpenAlex work metadata. Humans own the decisions; agents run, explain and extend the pipeline.

## Golden rules

1. **Never edit approved human inputs without being asked.** These are: `data/00_scope/*`, `data/02_keywords/keywords.csv`, `data/03_labels/labels.csv`, `data/04_query/query.yaml`. Propose changes as a new file in `runs/<run_id>/` (e.g. `keywords_proposed.csv`) and tell the human what changed and why.
2. **Never set `approved: true` in `data/04_query/query.yaml`.** Only a human does that.
3. **Run stages through the numbered scripts**, not ad-hoc code, so every run gets a run folder, metadata and a request log. If a script lacks something, improve the script.
4. **Do not spend API budget without checking the plan first.** Every API script prints the number of requests and the estimated cost before sending. For anything above $0.10, show the estimate to the human and wait for a go-ahead.
5. **Never commit or print secrets.** The API key is read from the `OPENALEX_API_KEY` environment variable. `.env` is git-ignored.
6. **Record decisions.** Any change to settings, thresholds or the method gets an entry in `docs/decisions.md` (date, decision, reason, evidence file).
7. **Keep it simple.** No new frameworks, databases or services. Prefer a few clear functions over abstractions. Plain CSV/YAML/JSONL.

## Where things are

- Settings, thresholds, budget: `config/project.yaml` (the only place for them; don't hard-code values in scripts).
- Shared code: `src/kwpipe/` — `config.py`, `runs.py`, `openalex.py`, `queries.py`, `keywords.py`, `metrics.py`.
- Stage scripts: `scripts/NN_*.py`, each with `--help`.
- Definitions of every metric: `docs/metrics.md`. Table schemas: `docs/data_contracts.md`.
- Known OpenAlex behaviour, prices and limits: `docs/openalex_notes.md`.
- Open work: `docs/backlog.md`.

## How to work on code

- Python ≥ 3.10. Install with `pip install -e ".[dev]"`; extraction extras with `pip install -e ".[extract]"`.
- Run `pytest` before and after changes. Add a test for every new function in `src/kwpipe/`.
- Scripts must stay runnable with `python scripts/NN_name.py --help`.
- Every script that calls the API must: use `kwpipe.openalex.OpenAlex` (logging, retries, budget guard, cache), create a run with `kwpipe.runs.start_run`, and support `--resume <run_id>`.
- Write outputs only to the run folder. Read inputs from `data/` or from an explicit `runs/<run_id>/…` path passed as an argument.
- Use UTF-8 everywhere. Check for non-ASCII characters in keywords (a past list had `ε` read as `╬╡`).
- Show the human code changes to review before applying them, unless they said otherwise.

## How to work with results

- Explain numbers in plain language and point to the file they came from.
- When proposing a keyword change, give the evidence (counts, gain, samples) and the rule from `docs/metrics.md` that applies.
- When labelling relevance samples, write your labels to a separate column (`label_agent`) with a one-line reason; never overwrite `label_human`.

## Human gates

| Gate | What the human approves | File |
|---|---|---|
| G1 | Topic definition, inclusion/exclusion criteria, seed papers | `data/00_scope/` |
| G2 | Keyword table (terms, groups, facets, status) | `data/02_keywords/keywords.csv` |
| G3 | Final query and its settings | `data/04_query/query.yaml` (`approved: true`) |
| G4 | Retrieved corpus accepted (counts, completeness checks) | entry in `docs/decisions.md` |
