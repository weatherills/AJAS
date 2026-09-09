"""Auto-Apply database layer (Cosmos schema + store).

Implements the Database PRD: auto_apply_attempts with an approval gate,
immutable apply_packages, resume variants and cover letters, form autofill,
vendor field mappings, submit_requests with per-vendor idempotency, append-only
status_events, and webhook_callbacks. The in-memory store is the rule engine;
Cosmos hydrates and persists the same documents.
"""

from app.auto_apply.constants import ATTEMPTS_CONTAINER
from app.auto_apply.containers import container_specs, ensure_auto_apply_containers
from app.auto_apply.errors import (
    AutoApplyConflictError,
    AutoApplyNotFoundError,
    AutoApplyStoreError,
    AutoApplyValidationError,
)
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.models import AutoApplyAttempt
from app.auto_apply.store import AutoApplyStore, get_auto_apply_store

__all__ = [
    "ATTEMPTS_CONTAINER",
    "AutoApplyAttempt",
    "AutoApplyConflictError",
    "AutoApplyNotFoundError",
    "AutoApplyStore",
    "AutoApplyStoreError",
    "AutoApplyValidationError",
    "InMemoryAutoApplyStore",
    "container_specs",
    "ensure_auto_apply_containers",
    "get_auto_apply_store",
]
