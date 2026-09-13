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

