# OpenAlex notes

What this pipeline relies on, as documented at https://help.openalex.org (checked November 2026). Re-check prices and limits before large runs.

## Access and cost

- Base URL `https://api.openalex.org`. API key free at openalex.org/settings/api; sent as `Authorization: Bearer <key>`.
- Free key: **$1/day** of usage, up to 30 requests/second. Without key: $0.10/day, 10/s. HTTP 429 = over budget or over the per-second limit.
- Prices per request: singleton (`/works/W123`) free · list/filter $0.0001 · search $0.001 · PDF $0.01. A request costs the same for 1 or 100 results.
- Responses report `meta.cost`. **Verify its unit with `00_smoke_test.py`** (credits vs. USD) and set `openalex.reported_cost_unit` in the config. 1 credit = $0.0001 (a list request = 1 credit, a search = 10).
- Sync filters (`from_updated_date`, …) need a paid plan.

## Querying

- `search.title_abstract_keywords=` (our default): title + abstract, plus works tagged with an OpenAlex keyword the search names. Same as OQL `about`.
- Bare words are **stemmed**; `"quoted phrases"` are **exact** (no stemming); `*` wildcard needs ≥3 characters before it and can't start a word. Capitalised `AND`, `OR`, `NOT` and parentheses are Boolean operators. No synonyms are ever added.
- Filters: `filter=a:x,b:y` (AND), `a:x|y` (OR, up to 100 values). Batch ID lookup: `filter=openalex:W1|W2|...` (≤100).
- `select=` limits returned fields (saves bandwidth, not credits). `per_page` max 100.
- Random sample: `sample=N&seed=S` (N ≤ 10,000) — reproducible with the same seed.
- `group_by=` returns counts per value (e.g. year); priced like the underlying list.
- `corpus=core` (default, ~324M works) · `all` (adds ~193M expansion works) · `expansion`.

## Paging

- Basic paging stops at 10,000 results. Use cursor paging: `cursor=*`, then `meta.next_cursor` until it is null.
- Don't cursor-page all of `/works`; use the snapshot for whole-database needs.

## Snapshot (if ever needed)

- `s3://openalex/data/{jsonl|parquet}/works/`, anonymous (`--no-sign-request`), quarterly, ~670 GB compressed for works (JSONL).
- Contains all corpora; filter `is_xpac = false` to match the API default. No search index; abstracts as inverted indexes.

## Gotchas seen in this project

- Garbled characters (`╬╡` for `ε`) are silently ignored by search and can make a term match far too much.
- Unquoted multi-word terms behave like AND of stemmed words anywhere in the text.
- Counts drift as OpenAlex updates; run a benchmark within one day and record dates.
- Group counts can't be summed to a corpus size (overlap); use the full union or de-duplicated IDs.

## The OpenAlex MCP connector (optional, for agents)

`https://mcp.openalex.org/mcp`. Useful free/cheap tools: `check_oql` (validate + price a query), `search_works` with `preview=true`, `find_keywords`, `keyword_search`, `get_work`. Each result includes canonical OQL and a reproduce URL.
