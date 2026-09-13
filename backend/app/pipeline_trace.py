"""End-to-end trace IDs for ingestion → match → apply."""

from __future__ import annotations

from uuid import uuid4

from app.request_context import current_request_id
from app.tracing import finish_span, start_span


def pipeline_trace_id() -> str:
    return current_request_id() or str(uuid4())


def trace_stage(stage: str, *, trace_id: str | None = None, **attrs: object) -> dict[str, object]:
    span = start_span(f"pipeline.{stage}", traceId=trace_id or pipeline_trace_id(), **attrs)
    if trace_id:
        span["traceId"] = trace_id
    return span


def complete_stage(span: dict[str, object], *, ok: bool = True, error: str | None = None) -> dict[str, object]:
    return finish_span(span, ok=ok, error=error)
