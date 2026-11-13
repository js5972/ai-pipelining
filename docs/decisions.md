# Decision log

One entry per decision that changes the method, settings, thresholds, keyword list or corpus. Newest at the bottom. Each entry: ID, date, decision, reason, evidence (file in `runs/` or `data/`), decided by.

---

### D-001 · 2026-11-09 · Use the OpenAlex API as the core of the pipeline
- **Decision:** API with cursor paging for retrieval; the official CLI is optional for fetching full records by ID; the full snapshot (~670 GB of works, quarterly) only if the corpus becomes very large or a frozen release is needed.
- **Reason:** keyword search runs server-side in the API; a keyword-defined topic is a small slice of OpenAlex; count requests make benchmarking almost free.
- **Decided by:** Juanita

### D-002 · 2026-11-09 · Two-phase retrieval
- **Decision:** phase 1 collects IDs from one combined query (search price, per 100 results); phase 2 fetches full records by ID in batches of 100 (list price).
- **Reason:** one combined query avoids paying for overlapping keyword results and removes de-duplication; the ID list is the frozen corpus definition.
- **Decided by:** Juanita

### D-003 · 2026-11-09 · Structure keywords as facets in the long run
- **Decision:** OR within a concept (facet), AND between concepts; a deep taxonomy is kept only as labels for analysis.
- **Reason:** generic finance words (yield, spread, premium, bond) have meanings in other fields; facets let general terms be used safely.
- **Decided by:** Juanita

### D-004 · 2026-11-10 · Benchmark the legacy keyword list first
- **Decision:** treat the old list (term, primary/alternative, group, category, usage recommendation) as the baseline before redesigning it.
- **Reason:** improvements need a fixed reference point.
- **Decided by:** Juanita

### D-005 · 2026-11-10 · Fix text encoding at the source (UTF-8)
- **Decision:** read keyword files as UTF-8; flag non-ASCII characters in every keyword check.
- **Reason:** one term contained `╬╡` (an `ε` decoded as code page 437) and returned the largest count in the list because the search ignored the garbled characters.
- **Decided by:** Juanita

### D-006 · 2026-11-10 · Quote multi-word terms
- **Decision:** `quote_phrases: true`. Phrases are searched as exact phrases.
- **Reason:** 27 of the 33 terms above 50,000 results were unquoted phrases whose words matched anywhere in titles/abstracts; quoting reduced counts substantially and no quoted phrase collapsed to near zero, so no plural/inflected alternatives were needed.
- **Evidence:** `section3b_settings.csv` (notebook run).
- **Decided by:** Juanita

### D-007 · 2026-11-10 · Keep the default search scope
- **Decision:** `search_param: search.title_abstract_keywords` (title + abstract + OpenAlex keywords the search names).
- **Reason:** title + abstract only gave the same counts.
- **Decided by:** Juanita

### D-008 · 2026-11-12 · Variant gain compares each alternative with all primaries of its group
- **Decision:** gain = count(P OR alternative) − count(P), where P = the group's primaries ORed.
- **Reason:** the legacy table links alternatives to groups, not to a specific primary; groups may have several primaries.
- **Decided by:** Juanita

### D-009 · 2026-11-13 · Restart as a plain-files repository for agent-assisted work
- **Decision:** numbered scripts, one config file, approved inputs in `data/`, generated outputs in `runs/`, human gates G1–G4.
- **Reason:** reproducibility, easy maintenance, and a clear split between agent work and human decisions.
- **Decided by:** Juanita

---

<!-- Template
### D-0NN · YYYY-MM-DD · Short title
- **Decision:**
- **Reason:**
- **Evidence:**
- **Decided by:**
-->
