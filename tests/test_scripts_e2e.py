"""Runs stages 4-6 end to end against the fake OpenAlex in conftest.py."""
import json
import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

from conftest import FakeSession

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture
def sandbox(monkeypatch, tmp_path, api_key):
    import kwpipe.openalex
    import kwpipe.runs
    monkeypatch.setattr(kwpipe.runs, "ROOT", tmp_path)
    monkeypatch.setattr(kwpipe.openalex.requests, "Session", FakeSession)
    return tmp_path


def run(script, *args, monkeypatch):
    monkeypatch.setattr(sys, "argv", [script, *args, "--yes"])
    runpy.run_path(str(SCRIPTS / script), run_name="__main__")


def latest(root, stage):
    return sorted((root / "runs").glob(f"*_{stage}"))[-1]


def test_stages_4_to_6(sandbox, keywords_csv, monkeypatch):
    run("04_term_counts.py", "--keywords", str(keywords_csv), monkeypatch=monkeypatch)
    tc = pd.read_csv(latest(sandbox, "term_counts") / "term_counts.csv")
    assert tc.set_index("term_id").loc["K0006", "flag_large"]

    run("05_variant_gain.py", "--keywords", str(keywords_csv), monkeypatch=monkeypatch)
    vg = pd.read_csv(latest(sandbox, "variant_gain") / "variant_gain.csv").set_index("term_id")
    assert vg.loc["K0002", "gain"] == 600 and vg.loc["K0002", "verdict"] == "niche"
    assert vg.loc["K0003", "verdict"] == "redundant"
    assert vg.loc["K0006", "verdict"] == "suspicious"

    run("06_group_unions.py", "--keywords", str(keywords_csv),
        "--term-counts", str(latest(sandbox, "term_counts") / "term_counts.csv"), monkeypatch=monkeypatch)
    meta = json.loads((latest(sandbox, "group_unions") / "run_metadata.json").read_text())
    assert meta["summary"]["full_union_count"] == len(set(range(0, 8600)) | set(range(20000, 120000)))
    assert meta["summary"]["facet_query_count"] == 0
    assert (latest(sandbox, "group_unions") / "query_draft.yaml").exists()
