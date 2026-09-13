"""Detect DOM/API shape drift between listing snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any

_PREVIOUS: dict[str, str] = {}


def _shape(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload)
        nested = {key: _shape(payload[key]) for key in list(payload)[:12]}
        return json.dumps({"keys": keys, "nested": nested}, sort_keys=True)
    if isinstance(payload, list):
        sample = payload[0] if payload else None
        return json.dumps({"list": True, "item": _shape(sample), "n": len(payload)}, sort_keys=True)
    return type(payload).__name__


def fingerprint(payload: Any) -> str:
    return hashlib.sha256(_shape(payload).encode()).hexdigest()[:16]


def detect_change(source: str, payload: Any) -> dict[str, object]:
    current = fingerprint(payload)
    previous = _PREVIOUS.get(source)
    _PREVIOUS[source] = current
    return {
        "source": source,
        "fingerprint": current,
        "changed": previous is not None and previous != current,
        "firstSeen": previous is None,
    }


def reset() -> None:
    _PREVIOUS.clear()
