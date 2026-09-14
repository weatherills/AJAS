"""Sprint 16 product helpers: search, apply, compare, a11y, i18n."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.sprint14.product import a11y_label, windowed
from app.sprint15.product import bulk_save, list_team_presets, save_preset, team_preset


_TEAMS: dict[str, list[dict[str, Any]]] = {}
_ARCHIVES: dict[str, list[str]] = {}
_HASHES: dict[str, str] = {}


def reset() -> None:
    _TEAMS.clear()
    _ARCHIVES.clear()
    _HASHES.clear()


def org_preset(*, org_id: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
    row = team_preset(team_id=f"org:{org_id}", name=name, filters=filters)
    _TEAMS.setdefault(org_id, []).append(row)
    return {**row, "orgId": org_id, "shared": True}


def list_org_presets(org_id: str) -> list[dict[str, Any]]:
    return list(_TEAMS.get(org_id) or list_team_presets(f"org:{org_id}"))


def phrase_search(items: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    raw = (q or "").strip()
    if not raw:
        return list(items)
    not_parts: list[str] = []
    must: list[str] = []
    buf = raw
    while "NOT " in buf.upper():
        idx = buf.upper().find("NOT ")
        after = buf[idx + 4 :].strip()
        token, _, rest = after.partition(" ")
        if token:
            not_parts.append(token.strip('"'))
        buf = (buf[:idx] + " " + rest).strip()
    phrases = re_phrases(buf)
    must.extend(phrases)
    leftover = re_strip_phrases(buf)
    must.extend(token for token in leftover.split() if token and token.upper() != "AND")
    out = []
    for row in items:
        blob = " ".join(str(v) for v in row.values()).lower()
        if all(part.lower() in blob for part in must) and all(part.lower() not in blob for part in not_parts):
            out.append(row)
    return out


def re_phrases(q: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r'"([^"]+)"', q or "")]


def re_strip_phrases(q: str) -> str:
    return re.sub(r'"[^"]+"', " ", q or "")


def density_mode(*, n: int, start: int = 0, compact: bool = True) -> dict[str, Any]:
    return {**windowed(n, start=start), "mode": "compact" if compact else "comfortable"}


def hiring_team(name: str) -> dict[str, Any]:
    return {"company": name, "panel": True, "live": False, "members": []}


def bulk_archive(ids: list[str], selected: list[str]) -> dict[str, Any]:
    archived = [item for item in selected if item in ids]
    _ARCHIVES["last"] = archived
    return {"archived": archived, "undo": archived}


def optional_warnings(site: str, provided: dict[str, str]) -> dict[str, Any]:
    optional = ["phone", "linkedin", "website"]
    missing = [key for key in optional if not provided.get(key)]
    return {"site": site, "warnings": missing, "ready": True}


def reading_level(text: str, *, target: int = 10) -> dict[str, Any]:
    words = [w for w in (text or "").split() if w]
    avg = sum(len(w) for w in words) / max(len(words), 1)
    grade = min(16, max(1, round(avg)))
    return {"grade": grade, "target": target, "ok": grade <= target}


def file_hash(name: str, body: bytes) -> dict[str, Any]:
    digest = sha256(body).hexdigest()[:16]
    prior = _HASHES.get(digest)
    _HASHES[digest] = name
    return {"hash": digest, "name": name, "dupe": prior is not None, "prior": prior}


def compare_three(left: dict[str, Any], mid: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(left) | set(mid) | set(right))
    rows = [
        {"field": key, "left": left.get(key), "mid": mid.get(key), "right": right.get(key)}
        for key in keys
    ]
    return {"rows": rows, "mode": "three"}


def search_webhook(*, url: str, query: str) -> dict[str, Any]:
    return {"url": url, "query": query, "channel": "webhook", "id": str(uuid4())}


def skip_links() -> dict[str, str]:
    return {"main": "#main", "nav": "#nav", "search": "#search"}


def currency_formats(*, locale: str = "en-US") -> dict[str, str]:
    return {"locale": locale, "currency": "¤#,##0.00", "date": "yyyy-MM-dd"}


def swipe_actions(*, width: int) -> dict[str, Any]:
    return {"enabled": width <= 640, "save": "right", "dismiss": "left"}


def a11y(kind: str) -> dict[str, str]:
    return a11y_label(kind)


def reuse_save(ids: list[str], selected: list[str]) -> dict[str, Any]:
    return bulk_save(ids, selected)


def reuse_preset(*, user_id: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
    return save_preset(user_id=user_id, name=name, filters=filters)
