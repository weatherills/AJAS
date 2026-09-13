"""Secret rotation with drift detection against the last known fingerprints."""

from __future__ import annotations

import hashlib
from typing import Any

_LAST: dict[str, str] = {}


def reset() -> None:
    _LAST.clear()


def fingerprint(value: str) -> str:
    return hashlib.sha256((value or "").encode()).hexdigest()[:16]


def rotate(name: str, new_value: str, *, previous: str | None = None) -> dict[str, Any]:
    prior = _LAST.get(name)
    expected = fingerprint(previous) if previous is not None else prior
    current = fingerprint(new_value)
    drifted = bool(prior and expected and prior != expected)
    _LAST[name] = current
    return {"name": name, "rotated": True, "drift": drifted, "fingerprint": current}
