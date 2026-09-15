"""Sprint 20 health and traces on top of Sprint 19."""

from __future__ import annotations

from typing import Any

from app.sprint19.ops import health_v8, traces_s19
from app.sprint20 import VERSION


def health_v9() -> dict[str, Any]:
    row = health_v8()
    return {**row, "schema": "ajas.health.v9", "sha": VERSION, "version": VERSION}


def traces_s20(stage: str, *, trace_id: str = "s20") -> dict[str, Any]:
    return traces_s19(stage, trace_id=trace_id)
