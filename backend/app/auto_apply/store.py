"""Auto-Apply store protocol and factory."""

from __future__ import annotations

from typing import Any, Protocol

from app.auto_apply.models import (
    ApplyPackage,
    AutoApplyAttempt,
    CoverLetter,
    FormAutofillValue,
    ResumeVariant,
    StatusEvent,
    SubmitRequest,
    VendorFieldMapping,
    WebhookCallback,
)


class AutoApplyStore(Protocol):
    def seed_default_mappings(self) -> list[VendorFieldMapping]: ...

    def create_attempt(self, user_id: str, **kwargs: Any) -> AutoApplyAttempt: ...

    def get_attempt(self, attempt_id: str, *, user_id: str) -> AutoApplyAttempt: ...

    def list_attempts(self, user_id: str, **kwargs: Any) -> list[AutoApplyAttempt]: ...

    def approve(self, user_id: str, attempt_id: str) -> AutoApplyAttempt: ...

    def queue(self, user_id: str, attempt_id: str) -> AutoApplyAttempt: ...

    def transition(self, user_id: str, attempt_id: str, status: str, **kwargs: Any) -> AutoApplyAttempt: ...

    def create_resume_variant(self, user_id: str, **kwargs: Any) -> ResumeVariant: ...

    def list_resume_variants(self, user_id: str) -> list[ResumeVariant]: ...

    def create_cover_letter(self, user_id: str, **kwargs: Any) -> CoverLetter: ...

    def put_package(self, user_id: str, auto_apply_id: str, **kwargs: Any) -> ApplyPackage: ...

    def get_package(self, auto_apply_id: str, *, user_id: str) -> ApplyPackage: ...

    def lock_package(self, user_id: str, auto_apply_id: str) -> ApplyPackage: ...

    def put_autofill(self, user_id: str, auto_apply_id: str, **kwargs: Any) -> FormAutofillValue: ...

    def list_autofill(self, user_id: str, auto_apply_id: str) -> list[FormAutofillValue]: ...

    def missing_required_fields(self, user_id: str, auto_apply_id: str) -> list[str]: ...

    def put_vendor_mapping(self, **kwargs: Any) -> VendorFieldMapping: ...

    def list_vendor_mappings(self, vendor: str | None = None) -> list[VendorFieldMapping]: ...

    def create_submit_request(self, user_id: str, auto_apply_id: str, **kwargs: Any) -> SubmitRequest: ...

    def complete_submit(self, user_id: str, submit_id: str, **kwargs: Any) -> SubmitRequest: ...

    def list_submits(self, user_id: str, auto_apply_id: str) -> list[SubmitRequest]: ...

    def list_status_events(self, user_id: str, auto_apply_id: str, **kwargs: Any) -> list[StatusEvent]: ...

    def ingest_webhook(self, **kwargs: Any) -> WebhookCallback: ...

    def list_webhooks(self, **kwargs: Any) -> list[WebhookCallback]: ...


def get_auto_apply_store() -> AutoApplyStore:
    from app.config import get_settings
    from app.auto_apply.memory import InMemoryAutoApplyStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryAutoApplyStore()
    from app.auto_apply.cosmos_store import CosmosAutoApplyStore
    from app.storage.cosmos import get_database

    return CosmosAutoApplyStore(get_database())
