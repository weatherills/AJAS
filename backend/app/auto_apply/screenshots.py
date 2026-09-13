"""Apply submit-step screenshot metadata (no live site capture)."""

from __future__ import annotations

from typing import Any

_STEPS: dict[str, list[dict[str, Any]]] = {}


def capture_step(request_id: str, name: str, *, note: str = "") -> dict[str, Any]:
    step = {"name": name, "note": note, "kind": "screenshot-stub"}
    _STEPS.setdefault(request_id, []).append(step)
    return step


def for_request(request_id: str) -> list[dict[str, Any]]:
    return list(_STEPS.get(request_id, []))


def reset() -> None:
    _STEPS.clear()
