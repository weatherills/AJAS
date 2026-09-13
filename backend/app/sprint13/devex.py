"""Local worker hot-reload policy and queue emulator scripts."""

from __future__ import annotations

from typing import Any

_QUEUES: dict[str, list[dict[str, Any]]] = {}
_RELOAD: dict[str, Any] = {}


def reset() -> None:
    _QUEUES.clear()
    _RELOAD.clear()


def hot_reload_policy() -> dict[str, Any]:
    return {
        "watch": ["backend/app", "backend/function_app.py"],
        "debounceMs": 400,
        "restartWorkers": True,
        "stable": True,
        "exclude": ["**/__pycache__/**", "**/.venv/**"],
    }


def mark_reload(worker: str) -> dict[str, Any]:
    _RELOAD[worker] = {"worker": worker, "restarts": _RELOAD.get(worker, {}).get("restarts", 0) + 1}
    return _RELOAD[worker]


def enqueue_local(queue: str, payload: dict[str, Any]) -> dict[str, Any]:
    _QUEUES.setdefault(queue, []).append(payload)
    return {"queue": queue, "depth": len(_QUEUES[queue])}


def drain_local(queue: str) -> list[dict[str, Any]]:
    items = list(_QUEUES.get(queue) or [])
    _QUEUES[queue] = []
    return items


def emulator_scripts() -> list[str]:
    return ["scripts/s13_queue_emulator.py", "scripts/ajas.py seed"]
