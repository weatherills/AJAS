"""Queue worker dispatch: schema validation, backpressure, poison/DLQ."""

from __future__ import annotations

from typing import Any

from app.dlq import enqueue as dlq_enqueue
from app.queue_backpressure import backpressure
from app.slo_pipelines import record as record_slo
from app.storage.queue_schemas import (
    QueueSchemaError,
    parse_queue_message,
    poison_queue_name,
    should_dead_letter,
)

PIPELINE_FOR_QUEUE = {
    "crawl-runs": "ingest",
    "job-fetch": "ingest",
    "resume-parse": "ingest",
    "mail-ingest": "ingest",
    "match-compute": "match",
    "match-recalc": "match",
    "review-enrich": "match",
    "decision-events": "match",
    "learning-decisions": "match",
    "tuning-tasks": "match",
    "auto-apply-requests": "apply",
    "auto-apply-submits": "apply",
    "auto-apply-webhooks": "apply",
    "source-discovery": "ingest",
}


def handle_queue_payload(
    queue: str,
    body: dict[str, Any],
    *,
    dequeue_count: int = 1,
    depth: int = 0,
    poison_after: int = 5,
) -> dict[str, Any]:
    """Admit, validate, or dead-letter one queue payload. Does not run feature work."""
    pressure = backpressure(depth)
    pipeline = PIPELINE_FOR_QUEUE.get(queue, "ingest")
    if not pressure["admit"]:
        record_slo(pipeline, ok=False)
        return {"status": "shed", "queue": queue, **pressure}
    try:
        message = parse_queue_message(queue, body)
    except QueueSchemaError as exc:
        dead = dlq_enqueue(
            {"id": str(body.get("message_id") or f"{queue}-invalid"), "queue": queue, "reason": "schema", "error": str(exc)}
        )
        record_slo(pipeline, ok=False)
        return {
            "status": "dead-letter",
            "queue": queue,
            "target": poison_queue_name(queue),
            "dlqId": dead["id"],
            "reason": "schema",
        }
    if should_dead_letter(dequeue_count, poison_after=poison_after):
        dead = dlq_enqueue(
            {
                "id": message.message_id,
                "queue": queue,
                "reason": "poison",
                "dequeueCount": dequeue_count,
            }
        )
        record_slo(pipeline, ok=False)
        return {
            "status": "poison",
            "queue": queue,
            "target": poison_queue_name(queue),
            "dlqId": dead["id"],
            "reason": "poison",
        }
    record_slo(pipeline, ok=True)
    return {"status": "ok", "queue": queue, "message": message.model_dump(), **pressure}
