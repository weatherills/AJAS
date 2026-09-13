"""Mute noisy adapters so ingestion alerts stop paging."""

from __future__ import annotations

_MUTED: set[str] = set()


def reset() -> None:
    _MUTED.clear()


def mute(source: str) -> dict[str, object]:
    name = (source or "").strip().lower()
    if name:
        _MUTED.add(name)
    return {"source": name, "muted": True}


def unmute(source: str) -> dict[str, object]:
    name = (source or "").strip().lower()
    _MUTED.discard(name)
    return {"source": name, "muted": False}


def is_muted(source: str) -> bool:
    return (source or "").strip().lower() in _MUTED


def listing() -> list[str]:
    return sorted(_MUTED)
