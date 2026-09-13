"""Per-site automation caps and consent gates."""

from __future__ import annotations

DEFAULT_DAILY_CAP = 20

_USAGE: dict[str, int] = {}
_CONSENT: dict[str, bool] = {}


def set_consent(site: str, allowed: bool) -> None:
    _CONSENT[site] = bool(allowed)


def allow(site: str, *, cap: int = DEFAULT_DAILY_CAP) -> dict[str, object]:
    if not _CONSENT.get(site, False):
        return {"allowed": False, "reason": "consent", "used": _USAGE.get(site, 0), "cap": cap}
    used = _USAGE.get(site, 0)
    if used >= cap:
        return {"allowed": False, "reason": "cap", "used": used, "cap": cap}
    _USAGE[site] = used + 1
    return {"allowed": True, "reason": "ok", "used": used + 1, "cap": cap}


def reset() -> None:
    _USAGE.clear()
    _CONSENT.clear()
