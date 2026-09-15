"""Sprint 19 health and traces on top of Sprint 18."""

from __future__ import annotations

from typing import Any

from app.sprint18.ops import health_v7, traces_s18
from app.sprint19 import VERSION


def health_v8() -> dict[str, Any]:
    row = health_v7()
    return {**row, "schema": "ajas.health.v8", "sha": VERSION, "version": VERSION}


def traces_s19(stage: str, *, trace_id: str = "s19") -> dict[str, Any]:
    return traces_s18(stage, trace_id=trace_id)
