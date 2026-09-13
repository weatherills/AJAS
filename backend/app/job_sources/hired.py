"""Hired fixture adapter with token auth and CAPTCHA fail-closed.

Live Hired HTML scraping and CAPTCHA solving are out of scope. When a fixture
page looks like a CAPTCHA challenge, ingest returns no jobs and records
needs_manual — AJAS never bypasses CAPTCHA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.config import get_settings
from app.job_sources.boards import load_fixture_jobs

_SESSION: dict[str, str] = {}


@dataclass(frozen=True)
class HiredAuth:
    token_present: bool
    captcha: bool
    action: str
    bypass: bool


def remember_token(token: str) -> None:
    value = (token or "").strip()
    if not value:
        _SESSION.pop("token", None)
        return
    _SESSION["token"] = value


def clear_token() -> None:
    _SESSION.clear()


def active_token() -> str:
    if _SESSION.get("token"):
        return _SESSION["token"]
    settings = get_settings()
    return str(getattr(settings, "hired_api_token", "") or "").strip()


def auth_gate(payload: Any) -> HiredAuth:
    captcha = detect_captcha(payload)
    hit = bool(captcha["captcha"])
    token_ok = bool(active_token())
    if hit:
        return HiredAuth(token_ok, True, "needs_manual", False)
    if not token_ok:
        return HiredAuth(False, False, "needs_auth", False)
    return HiredAuth(True, False, "continue", False)


def hired_jobs(payload: Any, *, listing_url: str | None = None, html: str | None = None) -> list[dict[str, Any]]:
    gate = auth_gate(html if html is not None else payload)
    if gate.action != "continue":
        return []
    return load_fixture_jobs("hired", payload, listing_url=listing_url)
