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

# === S15-04 ===

def test_linkedin_jobs_adapter_v1_fixture_only():
    from app.sprint15.ingest import linkedin_v1, reset
    reset()
    out = linkedin_v1({"jobs": [{"id": "l1", "title": "Staff"}]})
    assert out["live"] is False
    assert out["flag"] is False

# === S15-05 ===

def test_google_for_jobs_adapter_v1():
    from app.sprint15.ingest import google_jobs_v1, reset
    reset()
    out = google_jobs_v1({"jobs": [{"id": "g1", "title": "SWE"}]})
    assert out["flag"] is False

# === S15-06 ===

def test_otta_adapter_v1():
    from app.sprint15.ingest import otta_v1, reset
    reset()
    out = otta_v1({"jobs": [{"id": "o1", "title": "Otta Role"}]})
    assert out["source"] == "otta"

# === S15-07 ===

def test_yc_work_at_a_startup_adapter_v1():
    from app.sprint15.ingest import reset, yc_v1
    reset()
    out = yc_v1({"jobs": [{"id": "y1", "title": "YC Eng"}]})
    assert out["live"] is False

# === S15-08 ===

def test_flexjobs_adapter_v1():
    from app.sprint15.ingest import flexjobs_v1, reset
    reset()
    out = flexjobs_v1({"jobs": [{"id": "f1", "title": "Flex"}]})
    assert out["flag"] is False

# === S15-09 ===

def test_simplyhired_adapter_v1():
    from app.sprint15.ingest import reset, simplyhired_v1
    reset()
    out = simplyhired_v1({"jobs": [{"id": "s1", "title": "Simply"}]})
    assert out["jobs"]

# === S15-10 ===

def test_careerbuilder_adapter_v1():
    from app.sprint15.ingest import careerbuilder_v1, reset
    reset()
    out = careerbuilder_v1({"jobs": [{"id": "c1", "title": "CB"}]})
    assert out["live"] is False and out["flag"] is False

