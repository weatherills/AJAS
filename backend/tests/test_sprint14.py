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

# === S14-06 ===

def test_weworkremotely_adapter_v1():
    from app.sprint14.ingest import reset, wwr_v1

    reset()
    out = wwr_v1(html="<article data-ajas-job data-title='WWR' data-company='Co' data-apply='https://x'></article>")
    assert out["flag"] is False
    assert out["live"] is False

# === S14-07 ===

def test_workable_adapter_v1():
    from app.sprint14.ingest import reset, workable_v1

    reset()
    out = workable_v1({"results": [{"id": "w1", "title": "Workable"}]})
    assert out["jobs"][0]["via"] == "json"

# === S14-08 ===

def test_greenhouse_company_board_crawler():
    from app.sprint14.ingest import greenhouse_board, reset

    reset()
    html = (FIXTURES / "greenhouse_career.html").read_text()
    out = greenhouse_board(html)
    assert out["crawler"] == "fixture"
    assert out["live"] is False
    assert any("Staff" in str(job.get("title")) for job in out["jobs"])

# === S14-09 ===

def test_lever_company_board_crawler():
    from app.sprint14.ingest import lever_board, reset

    reset()
    html = (FIXTURES / "lever_career.html").read_text()
    out = lever_board(html)
    assert out["source"] == "lever"
    assert out["live"] is False

# === S14-10 ===

def test_ashby_company_board_crawler():
    from app.sprint14.ingest import ashby_board, reset

    reset()
    out = ashby_board(payload={"jobs": [{"id": "a1", "title": "Ashby Role"}]})
    assert out["crawler"] == "fixture"
    assert out["flag"] is False

# === S14-11 ===

def test_source_adapter_bot_challenge_auto_detect_fallback():
    from app.sprint14.ingest import bot_challenge, reset

    reset()
    hit = bot_challenge("hcaptcha challenge")
    assert hit["captcha"] is True and hit["bypass"] is False and hit["fallback"] == "fixture"
    ok = bot_challenge("normal job html")
    assert ok["ok"] is True and ok["bypass"] is False

# === S14-12 ===

def test_source_adapter_rotating_proxies_abstraction_health():
    from app.sprint14.ingest import proxy_health, reset

    reset()
    row = proxy_health("http://proxy.ajas.local:8080")
    assert row["healthy"] is True
    assert row["active"]

