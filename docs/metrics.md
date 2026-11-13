# Metric definitions

All counts are OpenAlex `meta.count` values: the number of works **matching** a query. Matching is not relevance; relevance is measured separately (stage 7).

## Term counts (stage 4)

| Column | Definition |
|---|---|
| `count` | works matching the term, searched as `search_term` (phrases quoted if `quote_phrases`) |
| `flag_zero` | `count == 0` → check spelling/encoding, then usually drop |
| `flag_large` | `count > thresholds.large_count` → generic term or homonym; check in stages 5–7 |
| `flag_syntax` | term contains quotes, brackets, `|`, `:`, a capitalised AND/OR/NOT, or a short wildcard |

## Variant gain (stage 5)

For each group, **P** = the group's primary terms ORed; **A** = one alternative.

| Column | Formula | Meaning |
|---|---|---|
| `count_primaries` | count(P) | what the primaries find together |
| `count_alt_alone` | count(A) | what the alternative finds on its own |
| `count_primaries_plus_alt` | count(P OR A) | union, overlap counted once |
| `gain` | count(P OR A) − count(P) | works only the alternative finds |
| `overlap_with_primaries` | count(A) − gain | works both find |
| `gain_vs_group` | gain ÷ count(P) | how much the alternative grows the group |
| `new_share_of_alt` | gain ÷ count(A) | how much of what the alternative finds is new (0–1) |

`new_share_of_alt` outside [0, 1] means the counts came from requests built differently → recheck.
`gain_vs_group` is relative: always read it next to the raw `gain`, especially for small groups.

### Verdict rules

Thresholds from `config/project.yaml` (`thresholds:`), applied in this order:

1. `count_alt_alone == 0` → **matches nothing**
2. `gain_vs_group < redundant_share` → **redundant**
3. `gain_vs_group >= large_gain_share`:
   - `new_share_of_alt >= mostly_new` → **suspicious** (large and mostly new: relevant work the primaries miss, a different concept, or noise → sample `A NOT P`)
   - otherwise → **strong synonym** (consider making it a primary)
4. otherwise:
   - `new_share_of_alt >= mostly_new` → **niche** (keep)
   - otherwise → **minor variant** (keep)

| | mostly overlapping | mostly new |
|---|---|---|
| grows group ≥ large_gain_share | strong synonym | suspicious |
| grows group between the two thresholds | minor variant | niche |
| grows group < redundant_share | redundant | redundant |

## Group unions (stage 6)

| Column | Definition |
|---|---|
| `union_count` | count of all the group's terms ORed |
| `sum_term_counts` | sum of the individual term counts (if a term-count run is given) |
| `overlap_ratio` | `sum_term_counts ÷ union_count`; 1 = no overlap, higher = terms find the same works |
| full union | all approved terms ORed: the **baseline corpus size** (not the sum of group counts, which double-counts) |

## Relevance (stage 7)

| Measure | Definition |
|---|---|
| seed recall | seeds found by a query ÷ seeds resolvable in OpenAlex; reported separately for `extraction` and `evaluation` seeds |
| precision (estimate) | relevant ÷ labelled, on a seeded random sample; ±15 points at n≈30, ±10 at n≈100 |
| agent–human agreement | share of samples where `label_agent == label_human` |
