# Data contracts

All files are UTF-8. CSV files have a header row. Empty cells mean "not set".

## `data/00_scope/seeds.csv`

| Column | Required | Values |
|---|---|---|
| `seed_id` | yes | short ID, e.g. `S001` |
| `doi` | one of `doi` / `openalex_id` | `10.xxxx/...` (no `https://doi.org/` prefix needed) |
| `openalex_id` | one of `doi` / `openalex_id` | `W123...` |
| `title` | no | for humans |
| `role` | yes | `extraction` or `evaluation` (held out) |
| `notes` | no | |

## `data/02_keywords/keywords.csv` — the keyword table

| Column | Required | Values |
|---|---|---|
| `term_id` | yes | stable ID, e.g. `K0001`; never reused |
| `keyword_term` | yes | the term as written, no quotes (quoting is a setting) |
| `term_type` | yes | `primary` or `alternative` |
| `group` | yes | the concept this term names; alternatives belong to their primaries' group |
| `category` | no | broader topic, for summaries |
| `facet` | no | concept slot for the facet query (OR within, AND between) |
| `usage_rule` | no | free text, e.g. "only with group X" |
| `source` | no | `legacy`, `frequency`, `keybert`, `openalex`, `agent`, `expert`, `manual` |
| `status` | yes | `proposed`, `approved`, `rejected`, `parked` — only `approved` rows are queried |
| `decided_by` | no | who set the status |
| `decided_on` | no | `YYYY-MM-DD` |
| `notes` | no | reason, evidence file |

Legacy mapping (`00_import_legacy_keywords.py`): `primary_group → group`, `usage_recommendation → usage_rule`.

## `data/03_labels/labels.csv` — relevance labels (accumulating)

| Column | Values |
|---|---|
| `work_id` | `W123...` |
| `title` | |
| `query_name` | which query/sample the work came from |
| `label_human` | `relevant`, `not_relevant`, `unsure` |
| `label_agent` | same values, optional |
| `agent_reason` | one line, optional |
| `labelled_by`, `labelled_on` | |
| `sample_run_id` | run folder the sample came from |

## `data/04_query/query.yaml` — the frozen query (gate G3)

See the template in the file. Retrieval uses the `settings` stored here, not `config/project.yaml`, so a frozen query stays reproducible even if the config changes later.

## Run folders: `runs/<YYYYMMDDTHHMMSSZ>_<stage>/`

| File | Content |
|---|---|
| `run_metadata.json` | stage, timestamps, git commit and dirty flag, config path + SHA-256 + snapshot, input file hashes, package versions, summary |
| `request_log.jsonl` | one line per API request: params, status, retries, timings, count, reported cost, estimated USD cost, error |
| `cache.jsonl` | successful responses for small requests (counts, samples), so `--resume` never pays twice |
| stage outputs | CSV/YAML/JSONL as listed in `docs/workflow.md` |
