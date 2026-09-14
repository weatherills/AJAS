"""Sprint 17 health and traces on top of Sprint 16."""

from __future__ import annotations

from typing import Any

from app.sprint16.ops import health_v5, traces_s16
from app.sprint17 import VERSION


def health_v6() -> dict[str, Any]:
    row = health_v5()
    return {**row, "schema": "ajas.health.v6", "sha": VERSION, "version": VERSION}


def traces_s17(stage: str, *, trace_id: str = "s17") -> dict[str, Any]:
    return traces_s16(stage, trace_id=trace_id)
