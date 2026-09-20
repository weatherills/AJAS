"""Typed Storage Queue payloads plus dead-letter policy.

Workers validate with these models before doing work. Invalid JSON or a
failed Pydantic parse is dead-lettered immediately (no retry). Poison
messages that exceed ``poison_after`` dequeues go to ``{queue}-poison``.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA = "ajas.queue.v1"
POISON_SUFFIX = "-poison"
DEFAULT_POISON_AFTER = 5


class QueueMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ajas.queue.v1"] = SCHEMA
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    user_id: str | None = None
    enqueued_at: str
    attempt: int = 0


class CrawlRunMessage(QueueMessage):
    kind: Literal["crawl-run"] = "crawl-run"
    source_tenant_id: str
    source_id: str
    run_id: str


class JobFetchMessage(QueueMessage):
    kind: Literal["job-fetch"] = "job-fetch"
    source_tenant_id: str
    source_id: str
    run_id: str
    source_posting_id: str
    url: str


class ResumeParseMessage(QueueMessage):
    kind: Literal["resume-parse"] = "resume-parse"
    user_id: str
    resume_id: str
    blob_path: str
    mime_type: str


class MatchComputeMessage(QueueMessage):
    kind: Literal["match-compute"] = "match-compute"
    user_id: str
    resume_id: str
    job_id: str
    idempotency_key: str
    threshold_pct: int | None = None


class AutoApplyRequestMessage(QueueMessage):
    kind: Literal["auto-apply-request"] = "auto-apply-request"
    user_id: str
    auto_apply_id: str
    vendor: Literal["greenhouse", "lever", "manual"]


class AutoApplySubmitMessage(QueueMessage):
    kind: Literal["auto-apply-submit"] = "auto-apply-submit"
    user_id: str
    auto_apply_id: str
    vendor: Literal["greenhouse", "lever", "manual"]
    idempotency_key: str


class AutoApplyWebhookMessage(QueueMessage):
    kind: Literal["auto-apply-webhook"] = "auto-apply-webhook"
    vendor: Literal["greenhouse", "lever", "manual"]
    vendor_application_id: str
    dedupe_key: str
    payload_blob_uri: str | None = None


class MailIngestMessage(QueueMessage):
    kind: Literal["mail-ingest"] = "mail-ingest"
    email_account_id: str
    user_id: str
    graph_message_id: str | None = None
    mode: Literal["webhook", "poll", "both"] = "both"


class DecisionEventMessage(QueueMessage):
    kind: Literal["decision-event"] = "decision-event"
    user_id: str
    match_id: str
    decision_id: str
    decision: Literal["approve", "reject"]


class ReviewEnrichMessage(QueueMessage):
    kind: Literal["review-enrich"] = "review-enrich"
    user_id: str
    match_id: str


class LearningDecisionMessage(QueueMessage):
    kind: Literal["learning-decision"] = "learning-decision"
    user_id: str
    recommendation_id: str
    decision: Literal["approve", "reject", "skip"]


class TuningTaskMessage(QueueMessage):
    kind: Literal["tuning-task"] = "tuning-task"
    user_id: str | None = None
    weight_config_id: str
    reason: str = "auto"


class MatchRecalcMessage(QueueMessage):
    kind: Literal["match-recalc"] = "match-recalc"
    user_id: str
    reason: str = "threshold-change"


class SourceDiscoveryMessage(QueueMessage):
    kind: Literal["source-discovery"] = "source-discovery"
    user_id: str
    greenhouse_enabled: bool
    lever_enabled: bool


QUEUE_SCHEMAS: dict[str, type[QueueMessage]] = {
    "crawl-runs": CrawlRunMessage,
    "job-fetch": JobFetchMessage,
    "resume-parse": ResumeParseMessage,
    "match-compute": MatchComputeMessage,
    "auto-apply-requests": AutoApplyRequestMessage,
    "auto-apply-submits": AutoApplySubmitMessage,
    "auto-apply-webhooks": AutoApplyWebhookMessage,
    "mail-ingest": MailIngestMessage,
    "decision-events": DecisionEventMessage,
    "review-enrich": ReviewEnrichMessage,
    "learning-decisions": LearningDecisionMessage,
    "tuning-tasks": TuningTaskMessage,
    "match-recalc": MatchRecalcMessage,
    "source-discovery": SourceDiscoveryMessage,
}


def queue_names() -> tuple[str, ...]:
    return tuple(QUEUE_SCHEMAS.keys())


def poison_queue_name(queue: str) -> str:
    if queue.endswith(POISON_SUFFIX):
        return queue
    return f"{queue}{POISON_SUFFIX}"


def all_queue_names() -> tuple[str, ...]:
    names = list(queue_names())
    names.extend(poison_queue_name(name) for name in queue_names())
    return tuple(names)


def should_dead_letter(dequeue_count: int, *, poison_after: int = DEFAULT_POISON_AFTER) -> bool:
    return int(dequeue_count) >= int(poison_after)


class QueueSchemaError(ValueError):
    """Payload failed validation and must be dead-lettered without retry."""

    dead_letter = True


def parse_queue_message(queue: str, body: dict[str, Any]) -> QueueMessage:
    model = QUEUE_SCHEMAS.get(queue)
    if model is None:
        raise QueueSchemaError(f"unknown queue {queue}")
    try:
        return model.model_validate(body)
    except ValidationError as exc:
        raise QueueSchemaError(str(exc)) from exc


def encode_queue_message(message: QueueMessage) -> dict[str, Any]:
    return message.model_dump()


def config_queue_names() -> tuple[str, ...]:
    """Queue names declared on ``Settings`` (fields ending in ``_queue``)."""
    from app.config import get_settings

    settings = get_settings()
    names = []
    for field_name, value in settings.model_dump().items():
        if field_name.endswith("_queue") and isinstance(value, str) and value.strip():
            names.append(value.strip())
    return tuple(sorted(set(names)))
