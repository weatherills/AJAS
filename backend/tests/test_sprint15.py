from __future__ import annotations

# === S15-01 ===

def test_indeed_adapter_v1_pagination_backoff():
    from app.flags import feature_enabled
    from app.sprint15 import VERSION
    from app.features.health import _status_payload
    from app.sprint15.ingest import indeed_v1, reset

    reset()
    assert VERSION == "sprint15"
    assert _status_payload()["version"] == "sprint15"
    assert feature_enabled("indeed_adapter") is False
    out = indeed_v1({"jobs": [{"id": "1", "title": "Backend"}, {"id": "2", "title": "Data"}]})
    assert out["live"] is False and out["flag"] is False
    assert len(out["jobs"]) >= 2
    assert out["pages"] is True

