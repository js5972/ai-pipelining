"""Stage 7: seed recall and random samples for labelling.

- Seed recall: which seeds (data/00_scope/seeds.csv) each query finds, split by role
  (extraction vs. held-out evaluation). Missed evaluation seeds are the gaps to study.
- Samples: a seeded random sample of each query's results (not the top hits), written as a
  labelling sheet. Add finished labels to data/03_labels/labels.csv.

Queries come from a query file (data/04_query/query.yaml, or a run's query_draft.yaml) and use its settings.
"""
import argparse

import pandas as pd
import yaml

from kwpipe.config import load_config, resolve
from kwpipe.metrics import reconstruct_abstract
from kwpipe.openalex import OpenAlex, OpenAlexError
from kwpipe.runs import finish_run, start_run

SAMPLE_FIELDS = "id,display_name,publication_year,primary_location,primary_topic,abstract_inverted_index"


def short_id(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def resolve_seeds(oa, seeds: pd.DataFrame) -> pd.DataFrame:
    """Fill openalex_id from DOI with free singleton lookups."""
    seeds = seeds.copy()
    for i, r in seeds.iterrows():
        if r["openalex_id"] or not r["doi"]:
            continue
        doi = r["doi"].removeprefix("https://doi.org/")
        try:
            seeds.at[i, "openalex_id"] = short_id(oa.get(f"works/doi:{doi}", {"select": "id"}, label="seed")["id"])
        except OpenAlexError:
            seeds.at[i, "openalex_id"] = ""
    return seeds


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query-file", default="data/04_query/query.yaml")
    ap.add_argument("--seeds", default="data/00_scope/seeds.csv")
    ap.add_argument("--no-samples", action="store_true")
    ap.add_argument("--resume")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--config", default="config/project.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    qf = yaml.safe_load(resolve(args.query_file).read_text(encoding="utf-8"))
    run_dir, meta = start_run("relevance", cfg, inputs={"query_file": args.query_file, "seeds": args.seeds},
                              resume=args.resume, params=vars(args))
    oa = OpenAlex(cfg, run_dir, settings=qf.get("settings"))

    queries = {f"q{i}": q for i, q in enumerate(qf["queries"], 1)}
    if qf.get("alternative_facet_query"):
        queries["facet"] = qf["alternative_facet_query"]
    if not queries:
        raise SystemExit("The query file has no queries.")

    seeds = pd.read_csv(resolve(args.seeds), dtype=str, keep_default_na=False)
    size = min(cfg["sampling"]["size"], 100)
    n_req = len(queries) * ((len(seeds) + 99) // 100 + (0 if args.no_samples else 1))
    if not oa.confirm(n_req, n_req * cfg["prices_usd"]["search"], args.yes):
        return

    # --- seed recall ---
    seeds = resolve_seeds(oa, seeds)
    ids = [s for s in seeds["openalex_id"] if s]
    found = {name: set() for name in queries}
    for name, q in queries.items():
        for i in range(0, len(ids), 100):
            batch = "|".join(ids[i:i + 100])
            res = oa.get("works", oa.search_params(q, filter=f"openalex:{batch}", per_page=100, select="id"),
                         label=f"seed recall {name}")
            found[name] |= {short_id(w["id"]) for w in res["results"]}
    recall = seeds[["seed_id", "doi", "openalex_id", "title", "role"]].copy()
    for name in queries:
        recall[f"found_{name}"] = recall["openalex_id"].isin(found[name])
    recall["found_any"] = recall[[f"found_{n}" for n in queries if n != "facet"]].any(axis=1)
    recall.to_csv(run_dir / "seed_recall.csv", index=False, encoding="utf-8")

    resolvable = recall[recall["openalex_id"] != ""]
    by_role = resolvable.groupby("role")["found_any"].agg(["sum", "count"]).reset_index()
    print("Seed recall (union of main queries):\n", by_role.to_string(index=False))
    gaps = resolvable[(resolvable["role"] == "evaluation") & ~resolvable["found_any"]]
    if len(gaps):
        print(f"Missed evaluation seeds (gaps): {len(gaps)} -> seed_recall.csv")

    # --- samples for labelling ---
    if not args.no_samples:
        for name, q in queries.items():
            res = oa.get("works", oa.search_params(q, sample=size, seed=cfg["sampling"]["seed"],
                                                   per_page=size, select=SAMPLE_FIELDS), label=f"sample {name}")
            rows = [{
                "work_id": short_id(w["id"]), "title": w.get("display_name"), "year": w.get("publication_year"),
                "source": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                "field": ((w.get("primary_topic") or {}).get("field") or {}).get("display_name"),
                "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
                "query_name": name, "label_human": "", "label_agent": "", "agent_reason": "",
                "labelled_by": "", "labelled_on": "", "sample_run_id": run_dir.name,
            } for w in res["results"]]
            pd.DataFrame(rows).to_csv(run_dir / f"sample_{name}.csv", index=False, encoding="utf-8")

    finish_run(run_dir, meta, {
        "queries": list(queries), "seeds": len(seeds), "seeds_resolved": len(resolvable),
        "recall_by_role": {r["role"]: f"{int(r['sum'])}/{int(r['count'])}" for _, r in by_role.iterrows()},
        "evaluation_gaps": gaps["seed_id"].tolist(), "spent_usd": round(oa.spent_usd, 4)})


if __name__ == "__main__":
    main()
