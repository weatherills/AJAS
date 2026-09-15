"""Sprint 18 health and traces on top of Sprint 17."""

from __future__ import annotations

from typing import Any

from app.sprint17.ops import health_v6, traces_s17
from app.sprint18 import VERSION


def health_v7() -> dict[str, Any]:
    row = health_v6()
    return {**row, "schema": "ajas.health.v7", "sha": VERSION, "version": VERSION}


def traces_s18(stage: str, *, trace_id: str = "s18") -> dict[str, Any]:
    return traces_s17(stage, trace_id=trace_id)
