import json

import pytest

from conftest import FakeSession
from kwpipe.openalex import BudgetExceeded, OpenAlex


def test_count_logs_caches_and_converts_cost(cfg, api_key, tmp_path):
    session = FakeSession()
    oa = OpenAlex(cfg, tmp_path, session=session)
    assert oa.count('"green bond"') == 8000
    assert oa.count('"green bond"') == 8000          # second call served from cache
    assert len(session.calls) == 1
    log = [json.loads(l) for l in (tmp_path / "request_log.jsonl").read_text().splitlines()]
    assert len(log) == 1 and log[0]["count"] == 8000
    assert abs(log[0]["cost_usd"] - 0.001) < 1e-12   # 10 credits * $0.0001
    assert "test-key" not in json.dumps(log)


def test_resume_reloads_cache(cfg, api_key, tmp_path):
    OpenAlex(cfg, tmp_path, session=FakeSession()).count("greenium")
    session = FakeSession()
    oa = OpenAlex(cfg, tmp_path, session=session)
    assert oa.count("greenium") == 300 and session.calls == []
    assert oa.spent_usd > 0


def test_budget_guard(cfg, api_key, tmp_path):
    cfg["budget"]["daily_usd"] = 0.0015
    cfg["budget"]["stop_fraction"] = 1.0
    oa = OpenAlex(cfg, tmp_path, session=FakeSession())
    oa.count("greenium")
    with pytest.raises(BudgetExceeded):
        oa.count("pricing")
