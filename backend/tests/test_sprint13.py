from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import azure.functions as func

# === S13-01 ===

def test_chaos_kill_switches_and_failure_injection():
    from app.features.health import _status_payload
    from app.sprint13 import VERSION
    from app.sprint13.platform import inject_failure, kill_switch, reset

    reset()
    assert VERSION == "sprint13"
    assert _status_payload()["version"] == "sprint13"
    assert kill_switch("ingest")["allow"] is True
    inject_failure("ingest")
    assert kill_switch("ingest")["killed"] is True
    assert kill_switch("ingest")["allow"] is False
    kill_switch("ingest", enabled=False)
    assert kill_switch("ingest")["allow"] is True

    req = func.HttpRequest(method="POST", url="http://localhost/api/v1/s13/kill", headers={"Authorization": "Bearer ada"}, params={}, body=b'{"name":"match","inject":true}')
    from app.features.sprint13 import kill as kill_http

    resp = kill_http(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body())["injected"] == "match"

# === S13-02 ===

def test_load_testing_ingest_and_match_throughput_targets():
    from app.sprint13.platform import load_report, reset

    reset()
    miss = load_report(ingest_qps=5, match_qps=10)
    assert miss["ingestOk"] is False
    assert miss["matchOk"] is False
    hit = load_report(ingest_qps=25, match_qps=80)
    assert hit["ingestOk"] is True
    assert hit["matchOk"] is True

# === S13-03 ===

def test_canary_releases_feature_flag_rollout_process():
    from app.sprint13.platform import canary, canary_assign, reset

    reset()
    cfg = canary(flag="fit-v2", percent=10)
    assert cfg["status"] == "rolling"
    canary(flag="fit-v2", percent=100)
    assert canary_assign("fit-v2", "anyone") == "treatment"
    canary(flag="fit-v2", percent=0)
    assert canary_assign("fit-v2", "anyone") == "control"

