"""Wellfound (AngelList) adapter authentication.

Live scraping is out of the Job Source PRD. Operators store an API token
(env `WELLFOUND_API_TOKEN` or `remember_token`) before fixture jobs load.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings

_SESSION: dict[str, str] = {}


@dataclass(frozen=True)
class WellfoundAuth:
    configured: bool
    method: str
    token_present: bool
    detail: str


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
    return str(getattr(settings, "wellfound_api_token", "") or "").strip()


def auth_status() -> WellfoundAuth:
    token = active_token()
    if token:
        return WellfoundAuth(True, "api_token", True, "Wellfound token is present. Fixture ingest only.")
    return WellfoundAuth(False, "api_token", False, "Set WELLFOUND_API_TOKEN or call remember_token().")


def require_auth() -> bool:
    return auth_status().token_present
