"""Auto-Apply database constants (Database PRD)."""

from typing import Final, Literal

Vendor = Literal["greenhouse", "lever", "manual"]
Mode = Literal["api", "manual_package"]
AttemptStatus = Literal[
    "draft",
    "queued",
    "submitting",
    "submitted",
    "succeeded",
    "failed",
    "needs_review",
    "rate_limited",
]
SubmitStatus = Literal["queued", "sent", "retrying", "succeeded", "failed"]
CoverSource = Literal["ai", "upload", "none"]
AutofillSource = Literal["resume", "profile", "user_input", "ai_inferred"]
StatusEventType = Literal[
    "created",
    "approved",
    "queued",
    "package_built",
    "submission_started",
    "submission_succeeded",
    "submission_failed",
    "vendor_ack",
    "vendor_rejected",
    "manually_submitted",
    "needs_review",
    "rate_limited",
]

VENDORS: Final[frozenset[str]] = frozenset({"greenhouse", "lever", "manual"})
MODES: Final[frozenset[str]] = frozenset({"api", "manual_package"})
ATTEMPT_STATUSES: Final[frozenset[str]] = frozenset(
    {"draft", "queued", "submitting", "submitted", "succeeded", "failed", "needs_review", "rate_limited"}
)
SUBMIT_STATUSES: Final[frozenset[str]] = frozenset({"queued", "sent", "retrying", "succeeded", "failed"})
COVER_SOURCES: Final[frozenset[str]] = frozenset({"ai", "upload", "none"})
AUTOFILL_SOURCES: Final[frozenset[str]] = frozenset({"resume", "profile", "user_input", "ai_inferred"})
EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "created",
        "approved",
        "queued",
        "package_built",
        "submission_started",
        "submission_succeeded",
        "submission_failed",
        "vendor_ack",
        "vendor_rejected",
        "manually_submitted",
        "needs_review",
        "rate_limited",
    }
)

TERMINAL_ATTEMPT: Final[frozenset[str]] = frozenset({"succeeded", "failed"})
QUEUED_OR_BEYOND: Final[frozenset[str]] = frozenset(
    {"queued", "submitting", "submitted", "succeeded", "failed", "needs_review", "rate_limited"}
)
READ_SCOPE: Final[str] = "read:auto-apply"
WRITE_SCOPE: Final[str] = "write:auto-apply"
REQUEST_QUEUE: Final[str] = "auto-apply-requests"
SUBMIT_QUEUE: Final[str] = "auto-apply-submits"
WEBHOOK_QUEUE: Final[str] = "auto-apply-webhooks"
POISON_DEQUEUE: Final[int] = 5
SAS_TTL_MINUTES: Final[int] = 10

STATUS_EVENTS_RETENTION_DAYS: Final[int] = 547  # 18 months
WEBHOOK_RETENTION_DAYS: Final[int] = 90

ATTEMPTS_CONTAINER: Final[str] = "auto_apply_attempts"
PACKAGES_CONTAINER: Final[str] = "apply_packages"
VARIANTS_CONTAINER: Final[str] = "resume_variants"
COVERS_CONTAINER: Final[str] = "cover_letters"
AUTOFILL_CONTAINER: Final[str] = "form_autofill_values"
MAPPINGS_CONTAINER: Final[str] = "vendor_field_mappings"
SUBMITS_CONTAINER: Final[str] = "submit_requests"
EVENTS_CONTAINER: Final[str] = "status_events"
WEBHOOKS_CONTAINER: Final[str] = "webhook_callbacks"

ATTEMPTS_PK: Final[str] = "/user_id"
PACKAGES_PK: Final[str] = "/auto_apply_id"
VARIANTS_PK: Final[str] = "/user_id"
COVERS_PK: Final[str] = "/user_id"
AUTOFILL_PK: Final[str] = "/auto_apply_id"
MAPPINGS_PK: Final[str] = "/vendor"
SUBMITS_PK: Final[str] = "/auto_apply_id"
EVENTS_PK: Final[str] = "/auto_apply_id"
WEBHOOKS_PK: Final[str] = "/vendor_application_id"

ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"queued", "failed"}),
    "queued": frozenset({"submitting", "failed", "needs_review"}),
    "submitting": frozenset({"submitted", "failed", "needs_review", "rate_limited"}),
    "submitted": frozenset({"succeeded", "failed", "needs_review"}),
    "rate_limited": frozenset({"queued", "submitting", "failed"}),
    "needs_review": frozenset({"queued", "failed", "submitted"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
}


def _policy(*composites: list[dict]) -> dict:
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/\"_etag\"/?"}],
        "compositeIndexes": list(composites),
    }


ATTEMPTS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/status", "order": "ascending"},
    ],
    [
        {"path": "/vendor", "order": "ascending"},
        {"path": "/source_application_id", "order": "ascending"},
    ],
)
PACKAGES_INDEXING: Final[dict] = _policy([{"path": "/auto_apply_id", "order": "ascending"}])
VARIANTS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/created_at", "order": "descending"},
    ]
)
COVERS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/source", "order": "ascending"},
    ]
)
AUTOFILL_INDEXING: Final[dict] = _policy(
    [
        {"path": "/auto_apply_id", "order": "ascending"},
        {"path": "/vendor", "order": "ascending"},
        {"path": "/field_key", "order": "ascending"},
    ]
)
MAPPINGS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/vendor", "order": "ascending"},
        {"path": "/normalized_key", "order": "ascending"},
    ]
)
SUBMITS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/auto_apply_id", "order": "ascending"},
        {"path": "/status", "order": "ascending"},
    ],
    [
        {"path": "/vendor", "order": "ascending"},
        {"path": "/vendor_request_id", "order": "ascending"},
    ],
    [
        {"path": "/vendor", "order": "ascending"},
        {"path": "/vendor_application_id", "order": "ascending"},
    ],
    [{"path": "/idempotency_key", "order": "ascending"}],
)
EVENTS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/auto_apply_id", "order": "ascending"},
        {"path": "/created_ts", "order": "descending"},
    ]
)
WEBHOOKS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/vendor", "order": "ascending"},
        {"path": "/vendor_application_id", "order": "ascending"},
    ],
    [{"path": "/dedupe_key", "order": "ascending"}],
)
