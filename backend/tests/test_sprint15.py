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

# === S15-02 ===

def test_dice_adapter_v1():
    from app.sprint15.ingest import dice_v1, reset
    reset()
    out = dice_v1({"jobs": [{"id": "d1", "title": "Dice Role"}]})
    assert out["source"] == "dice" and out["live"] is False

# === S15-03 ===

def test_wellfound_adapter_v1():
    from app.sprint15.ingest import reset, wellfound_v1
    reset()
    out = wellfound_v1({"jobs": [{"id": "w1", "title": "Founding Eng"}]})
    assert out["jobs"][0]["title"] == "Founding Eng"
    assert out["flag"] is False

