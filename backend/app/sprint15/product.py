"""Sprint 15 product helpers: search, apply, compare, a11y, i18n."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.sprint14.product import a11y_label, bulk_dismiss, list_presets, save_preset, windowed

_TEAMS: dict[str, list[dict[str, Any]]] = {}
_SAVES: dict[str, list[str]] = {}
_PREFS: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _TEAMS.clear()
    _SAVES.clear()
    _PREFS.clear()


def team_preset(*, team_id: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
    row = save_preset(user_id=f"team:{team_id}", name=name, filters=filters)
    _TEAMS.setdefault(team_id, []).append(row)
    return row


def list_team_presets(team_id: str) -> list[dict[str, Any]]:
    return list(_TEAMS.get(team_id) or list_presets(f"team:{team_id}"))


def boolean_search(items: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    parts = [token for token in (q or "").split() if token and token.upper() != "AND"]
    if not parts:
        return list(items)
    out = []
    for row in items:
        blob = " ".join(str(v) for v in row.values()).lower()
        if all(part.lower() in blob for part in parts):
            out.append(row)
    return out


def grid_mode(*, n: int, start: int = 0) -> dict[str, Any]:
    return {**windowed(n, start=start), "mode": "grid"}


def company_insights(name: str) -> dict[str, Any]:
    return {"company": name, "headcount": None, "live": False, "panel": True}


def bulk_save(ids: list[str], selected: list[str]) -> dict[str, Any]:
    saved = [item for item in selected if item in ids]
    _SAVES["last"] = saved
    return {"saved": saved, "undo": saved}


def required_fields(site: str, provided: dict[str, str]) -> dict[str, Any]:
    need = ["name", "email", "resume"]
    missing = [key for key in need if not provided.get(key)]
    return {"site": site, "missing": missing, "ready": not missing}


def cover_length(text: str, *, target: int = 120) -> dict[str, Any]:
    words = len((text or "").split())
    return {"words": words, "target": target, "ok": words <= target}


def detect_attachment(name: str) -> str:
    lowered = (name or "").lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".docx") or lowered.endswith(".doc"):
        return "docx"
    return "other"


def compare_table(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(left) | set(right))
    rows = [{"field": key, "left": left.get(key), "right": right.get(key), "diff": left.get(key) != right.get(key)} for key in keys]
    return {"rows": rows, "diffs": sum(1 for row in rows if row["diff"])}


def digest_schedule(*, hour: int, weekday: str = "mon") -> dict[str, Any]:
    return {"hour": hour, "weekday": weekday, "channel": "email", "id": str(uuid4())}


def shortcuts() -> dict[str, str]:
    return {"j": "next", "k": "prev", "s": "save", "d": "dismiss"}


def formats(*, locale: str = "en-US") -> dict[str, str]:
    return {"locale": locale, "date": "MMM d, yyyy", "number": "1,234"}


def bottom_nav(*, width: int) -> str:
    return "compact" if width <= 640 else "full"


def a11y(kind: str) -> dict[str, str]:
    return a11y_label(kind)


def undo_dismiss(ids: list[str], selected: list[str]) -> dict[str, Any]:
    return bulk_dismiss(ids, selected)
