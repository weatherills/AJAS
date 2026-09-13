from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "job_boards"

# === S14-01 ===

def test_ziprecruiter_adapter_v1_pagination_backoff():
    from app.flags import feature_enabled
    from app.sprint14 import VERSION
    from app.features.health import _status_payload
    from app.sprint14.ingest import reset, ziprecruiter_v1

    reset()
    assert VERSION == "sprint14"
    assert _status_payload()["version"] == "sprint14"
    assert feature_enabled("ziprecruiter_adapter") is False
    payload = json.loads((FIXTURES / "ziprecruiter.json").read_text())
    out = ziprecruiter_v1(payload)
    assert out["live"] is False
    assert out["flag"] is False
    assert len(out["jobs"]) >= 2

# === S14-02 ===

def test_monster_adapter_v1_html_api_hybrid():
    from app.sprint14.ingest import monster_v1, reset

    reset()
    out = monster_v1(payload={"jobs": [{"id": "1", "title": "Staff"}]}, html="<div>job posting</div>")
    assert "json" in out["paths"] and "html" in out["paths"]
    assert out["flag"] is False

# === S14-03 ===

def test_hired_adapter_v1_with_auth_session():
    from app.job_sources.hired import clear_token
    from app.sprint14.ingest import hired_v1, reset

    reset()
    clear_token()
    gated = hired_v1({"jobs": []})
    assert gated["bypass"] is False
    assert gated["action"] in {"needs_auth", "continue"}
    captcha = hired_v1({"jobs": []}, html="please complete the captcha")
    assert captcha["bypass"] is False
    assert captcha["action"] == "needs_manual"

# === S14-04 ===

def test_remoteok_adapter_v1():
    from app.sprint14.ingest import remoteok_v1, reset

    reset()
    out = remoteok_v1({"jobs": [{"id": "1", "title": "Remote Python"}]})
    assert out["jobs"][0]["title"] == "Remote Python"
    assert out["live"] is False

# === S14-05 ===

def test_remotive_adapter_v1():
    from app.sprint14.ingest import remotive_v1, reset

    reset()
    out = remotive_v1({"jobs": [{"id": "1", "title": "Remotive Role"}]})
    assert out["source"] == "remotive"
    assert out["flag"] is False

