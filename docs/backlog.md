# Backlog

Open work, roughly in priority order. Move items to `docs/decisions.md` when they change the method.

## Next

- [ ] Import the legacy keyword list (`00_import_legacy_keywords.py --status approved`) and re-run stages 4–6 as the baseline.
- [ ] Verify the unit of `meta.cost` with `00_smoke_test.py` and set `openalex.reported_cost_unit`.
- [ ] Fill `data/00_scope/scope.md` and `seeds.csv` (with held-out evaluation seeds).

## Validation

- [ ] **Usage rules:** map each `usage_rule` to the group(s) it refers to and test term alone vs. term AND group (strict baseline).
- [ ] **Group overlap:** pairwise AND counts between groups (within a category first; pairs grow with the square of groups).
- [ ] **Topic distribution:** `group_by` on primary topic field for large/suspicious terms; on-topic share using a list of field IDs in the config. Confirm the group-by field name with one request first.
- [ ] **Marginal samples:** sample `A NOT P` for `suspicious` alternatives (stage 7 option).
- [ ] **Year distribution:** `group_by=publication_year` per group to spot outdated terms.
- [ ] Corpus setting comparison (`core` vs `all`) on the final query only.

## Extraction

- [ ] OpenAlex keyword vocabulary as a third candidate source (connector `find_keywords`, or `/text/keywords` at $0.01/call).
- [ ] Lemmatised de-duplication of candidates (currently lowercase + simple plural folding).
- [ ] Agent-proposed alternatives: prompt and output columns, kept separate from human decisions.

## Agents

- [ ] Agent pre-labelling of samples (`label_agent`) and agreement report vs. `label_human`.
- [ ] A skill (Claude) / task guide (Codex) that runs stages 4–7 end-to-end and stops at gates.
- [ ] OQL as an alternative query path for long or nested queries (`check_oql` is free).

## Engineering

- [ ] Optional Parquet export of retrieved records with flattened fields.
- [ ] A `summary.py` that compares two runs (e.g. baseline vs. cleaned keywords).
