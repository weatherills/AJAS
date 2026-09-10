"""In-memory Auto-Apply store — the rule engine Cosmos hydrates into."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.auto_apply.constants import (
    ALLOWED_TRANSITIONS,
    ATTEMPT_STATUSES,
    AUTOFILL_SOURCES,
    COVER_SOURCES,
    EVENT_TYPES,
    MODES,
    QUEUED_OR_BEYOND,
    STATUS_EVENTS_RETENTION_DAYS,
    SUBMIT_STATUSES,
    TERMINAL_ATTEMPT,
    VENDORS,
    WEBHOOK_RETENTION_DAYS,
)
from app.auto_apply.errors import AutoApplyConflictError, AutoApplyNotFoundError, AutoApplyValidationError
from app.auto_apply.keys import is_expired, plus_days, utc_now
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
    new_id,
)


def _require_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AutoApplyValidationError(f"{field_name} is required", path=field_name)
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AutoApplyValidationError("value must be a string or null")
    stripped = value.strip()
    return stripped or None


def _one_of(value: str, allowed: frozenset[str], *, field_name: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in allowed:
        raise AutoApplyValidationError(f"invalid {field_name}", path=field_name)
    return cleaned


class InMemoryAutoApplyStore:
    def __init__(self, *, seed: bool = True) -> None:
        self._attempts: dict[str, AutoApplyAttempt] = {}
        self._packages: dict[str, ApplyPackage] = {}
        self._variants: dict[str, ResumeVariant] = {}
        self._covers: dict[str, CoverLetter] = {}
        self._autofill: dict[str, FormAutofillValue] = {}
        self._mappings: dict[str, VendorFieldMapping] = {}
        self._submits: dict[str, SubmitRequest] = {}
        self._events: dict[str, StatusEvent] = {}
        self._webhooks: dict[str, WebhookCallback] = {}
        if seed:
            self.seed_default_mappings()

    def seed_default_mappings(self) -> list[VendorFieldMapping]:
        defaults = [
            ("greenhouse", "full_name", "first_name", True, "split_first"),
            ("greenhouse", "email", "email", True, None),
            ("greenhouse", "phone", "phone", True, "e164"),
            ("lever", "full_name", "name", True, None),
            ("lever", "email", "email", True, None),
            ("lever", "phone", "phone", False, "e164"),
        ]
        now = utc_now()
        created: list[VendorFieldMapping] = []
        for vendor, normalized, vendor_key, required, transform in defaults:
            existing = next(
                (
                    row
                    for row in self._mappings.values()
                    if row.vendor == vendor and row.normalized_key == normalized
                ),
                None,
            )
            if existing:
                created.append(deepcopy(existing))
                continue
            row = VendorFieldMapping(
                vendor=vendor,
                normalized_key=normalized,
                vendor_field_key=vendor_key,
                required=required,
                transform=transform,
                created_at=now,
                updated_at=now,
            )
            self._mappings[row.id] = row
            created.append(deepcopy(row))
        return created

    def _event(self, attempt: AutoApplyAttempt, event_type: str, payload: dict[str, Any] | None = None) -> StatusEvent:
        event = StatusEvent(
            id=new_id(),
            auto_apply_id=attempt.id,
            user_id=attempt.user_id,
            event_type=_one_of(event_type, EVENT_TYPES, field_name="event_type"),
            payload=payload or {},
            created_ts=utc_now(),
        )
        self._events[event.id] = event
        return event

    def _owned_attempt(self, attempt_id: str, user_id: str) -> AutoApplyAttempt:
        row = self._attempts.get(attempt_id)
        if row is None or row.user_id != user_id:
            raise AutoApplyNotFoundError("attempt not found")
        return row

    def create_attempt(
        self,
        user_id: str,
        *,
        vendor: str,
        mode: str = "api",
        job_id: str | None = None,
        source_application_id: str | None = None,
        posting_url: str | None = None,
        resume_id: str | None = None,
    ) -> AutoApplyAttempt:
        owner = _require_str(user_id, field_name="user_id")
        vendor_name = _one_of(vendor, VENDORS, field_name="vendor")
        apply_mode = _one_of(mode, MODES, field_name="mode")
        job = _optional_str(job_id)
        source = _optional_str(source_application_id) or job
        url = _optional_str(posting_url)
        if not source and not url:
            raise AutoApplyValidationError("job_id or posting_url is required", path="job_id")
        for row in self._attempts.values():
            if row.user_id != owner:
                continue
            if row.status in TERMINAL_ATTEMPT:
                continue
            same_job = source and row.source_application_id == source
            same_url = url and row.posting_url == url
            if same_job or same_url:
                raise AutoApplyConflictError("in-flight attempt already exists for this job")
        now = utc_now()
        attempt = AutoApplyAttempt(
            user_id=owner,
            job_id=job,
            source_application_id=source,
            posting_url=url,
            vendor=vendor_name,
            mode=apply_mode if vendor_name != "manual" else "manual_package",
            status="draft",
            resume_id=_optional_str(resume_id),
            created_at=now,
            updated_at=now,
        )
        self._attempts[attempt.id] = attempt
        self._event(attempt, "created", {"vendor": attempt.vendor, "mode": attempt.mode})
        return deepcopy(attempt)

    def get_attempt(self, attempt_id: str, *, user_id: str) -> AutoApplyAttempt:
        return deepcopy(self._owned_attempt(attempt_id, user_id))

    def list_attempts(self, user_id: str, *, status: str | None = None, vendor: str | None = None) -> list[AutoApplyAttempt]:
        rows = [row for row in self._attempts.values() if row.user_id == user_id]
        if status:
            wanted = _one_of(status, ATTEMPT_STATUSES, field_name="status")
            rows = [row for row in rows if row.status == wanted]
        if vendor:
            wanted_vendor = _one_of(vendor, VENDORS, field_name="vendor")
            rows = [row for row in rows if row.vendor == wanted_vendor]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def approve(self, user_id: str, attempt_id: str) -> AutoApplyAttempt:
        attempt = self._owned_attempt(attempt_id, user_id)
        if attempt.status != "draft":
            raise AutoApplyConflictError("only draft attempts can be approved")
        now = utc_now()
        attempt.approved = True
        attempt.approved_ts = now
        attempt.updated_at = now
        self._event(attempt, "approved", {"approved_ts": now})
        return deepcopy(attempt)

    def queue(self, user_id: str, attempt_id: str) -> AutoApplyAttempt:
        attempt = self._owned_attempt(attempt_id, user_id)
        if not attempt.approved or not attempt.approved_ts:
            raise AutoApplyConflictError("attempt must be approved before it can be queued")
        missing = self.missing_required_fields(user_id, attempt_id)
        if missing:
            raise AutoApplyValidationError(
                f"required autofill fields missing: {', '.join(missing)}",
                path="form_autofill_values",
            )
        package = next((row for row in self._packages.values() if row.auto_apply_id == attempt.id), None)
        if package and not package.locked:
            package.locked = True
            package.updated_at = utc_now()
        return self._transition(attempt, "queued", event_type="queued")

    def transition(self, user_id: str, attempt_id: str, status: str, *, payload: dict[str, Any] | None = None) -> AutoApplyAttempt:
        attempt = self._owned_attempt(attempt_id, user_id)
        wanted = _one_of(status, ATTEMPT_STATUSES, field_name="status")
        if wanted in QUEUED_OR_BEYOND and (not attempt.approved or not attempt.approved_ts):
            raise AutoApplyConflictError("attempt must be approved before it can leave draft")
        event_map = {
            "queued": "queued",
            "submitting": "submission_started",
            "submitted": "vendor_ack",
            "succeeded": "submission_succeeded",
            "failed": "submission_failed",
            "needs_review": "needs_review",
            "rate_limited": "rate_limited",
        }
        return self._transition(attempt, wanted, event_type=event_map.get(wanted, "queued"), payload=payload)

    def _transition(
        self,
        attempt: AutoApplyAttempt,
        status: str,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> AutoApplyAttempt:
        allowed = ALLOWED_TRANSITIONS.get(attempt.status, frozenset())
        if status not in allowed:
            raise AutoApplyConflictError(f"cannot transition from {attempt.status} to {status}")
        attempt.status = status
        attempt.updated_at = utc_now()
        self._event(attempt, event_type, payload)
        return deepcopy(attempt)

    def create_resume_variant(self, user_id: str, *, label: str, blob_uri: str, resume_id: str | None = None) -> ResumeVariant:
        now = utc_now()
        row = ResumeVariant(
            user_id=_require_str(user_id, field_name="user_id"),
            resume_id=_optional_str(resume_id),
            label=_require_str(label, field_name="label"),
            blob_uri=_require_str(blob_uri, field_name="blob_uri"),
            created_at=now,
            updated_at=now,
        )
        self._variants[row.id] = row
        return deepcopy(row)

    def list_resume_variants(self, user_id: str) -> list[ResumeVariant]:
        rows = [row for row in self._variants.values() if row.user_id == user_id]
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def create_cover_letter(
        self,
        user_id: str,
        *,
        source: str = "none",
        blob_uri: str | None = None,
        body_text: str | None = None,
        auto_apply_id: str | None = None,
    ) -> CoverLetter:
        now = utc_now()
        row = CoverLetter(
            user_id=_require_str(user_id, field_name="user_id"),
            auto_apply_id=_optional_str(auto_apply_id),
            source=_one_of(source, COVER_SOURCES, field_name="source"),
            blob_uri=_optional_str(blob_uri),
            body_text=_optional_str(body_text),
            created_at=now,
            updated_at=now,
        )
        self._covers[row.id] = row
        return deepcopy(row)

    def get_cover_letter(self, cover_id: str, *, user_id: str) -> CoverLetter:
        row = self._covers.get(cover_id)
        if row is None or row.user_id != user_id:
            raise AutoApplyNotFoundError("cover letter not found")
        return deepcopy(row)

    def put_package(
        self,
        user_id: str,
        auto_apply_id: str,
        *,
        resume_variant_id: str | None = None,
        cover_letter_id: str | None = None,
        filled_fields_json: dict[str, Any] | None = None,
        deep_link_url: str | None = None,
        package_blob_uri: str | None = None,
    ) -> ApplyPackage:
        attempt = self._owned_attempt(auto_apply_id, user_id)
        existing = next((row for row in self._packages.values() if row.auto_apply_id == attempt.id), None)
        now = utc_now()
        if existing and existing.locked:
            raise AutoApplyConflictError("locked packages are immutable")
        if existing:
            existing.resume_variant_id = _optional_str(resume_variant_id) or existing.resume_variant_id
            existing.cover_letter_id = _optional_str(cover_letter_id) if cover_letter_id is not None else existing.cover_letter_id
            if filled_fields_json is not None:
                existing.filled_fields_json = dict(filled_fields_json)
            if deep_link_url is not None:
                existing.deep_link_url = _optional_str(deep_link_url)
            if package_blob_uri is not None:
                existing.package_blob_uri = _optional_str(package_blob_uri)
            existing.updated_at = now
            self._event(attempt, "package_built", {"package_id": existing.id})
            return deepcopy(existing)
        row = ApplyPackage(
            auto_apply_id=attempt.id,
            user_id=user_id,
            resume_variant_id=_optional_str(resume_variant_id),
            cover_letter_id=_optional_str(cover_letter_id),
            filled_fields_json=dict(filled_fields_json or {}),
            deep_link_url=_optional_str(deep_link_url),
            package_blob_uri=_optional_str(package_blob_uri),
            created_at=now,
            updated_at=now,
        )
        self._packages[row.id] = row
        self._event(attempt, "package_built", {"package_id": row.id})
        return deepcopy(row)

    def get_package(self, auto_apply_id: str, *, user_id: str) -> ApplyPackage:
        self._owned_attempt(auto_apply_id, user_id)
        row = next((item for item in self._packages.values() if item.auto_apply_id == auto_apply_id), None)
        if row is None:
            raise AutoApplyNotFoundError("package not found")
        return deepcopy(row)

    def lock_package(self, user_id: str, auto_apply_id: str) -> ApplyPackage:
        package = self.get_package(auto_apply_id, user_id=user_id)
        stored = self._packages[package.id]
        stored.locked = True
        stored.updated_at = utc_now()
        return deepcopy(stored)

    def put_autofill(
        self,
        user_id: str,
        auto_apply_id: str,
        *,
        vendor: str,
        field_key: str,
        value: str | None,
        required: bool = False,
        confidence: float | None = None,
        source: str = "resume",
    ) -> FormAutofillValue:
        attempt = self._owned_attempt(auto_apply_id, user_id)
        key = _require_str(field_key, field_name="field_key")
        vendor_name = _one_of(vendor, VENDORS, field_name="vendor")
        now = utc_now()
        existing = next(
            (
                row
                for row in self._autofill.values()
                if row.auto_apply_id == attempt.id and row.vendor == vendor_name and row.field_key == key
            ),
            None,
        )
        if existing:
            existing.value = _optional_str(value)
            existing.required = required
            existing.confidence = confidence
            existing.source = _one_of(source, AUTOFILL_SOURCES, field_name="source")
            existing.updated_at = now
            return deepcopy(existing)
        row = FormAutofillValue(
            auto_apply_id=attempt.id,
            user_id=user_id,
            vendor=vendor_name,
            field_key=key,
            value=_optional_str(value),
            required=required,
            confidence=confidence,
            source=_one_of(source, AUTOFILL_SOURCES, field_name="source"),
            created_at=now,
            updated_at=now,
        )
        self._autofill[row.id] = row
        return deepcopy(row)

    def list_autofill(self, user_id: str, auto_apply_id: str) -> list[FormAutofillValue]:
        self._owned_attempt(auto_apply_id, user_id)
        rows = [row for row in self._autofill.values() if row.auto_apply_id == auto_apply_id]
        return [deepcopy(row) for row in rows]

    def missing_required_fields(self, user_id: str, auto_apply_id: str) -> list[str]:
        return [
            row.field_key
            for row in self.list_autofill(user_id, auto_apply_id)
            if row.required and not (row.value and row.value.strip())
        ]

    def put_vendor_mapping(
        self,
        *,
        vendor: str,
        normalized_key: str,
        vendor_field_key: str,
        required: bool = False,
        transform: str | None = None,
    ) -> VendorFieldMapping:
        now = utc_now()
        vendor_name = _one_of(vendor, VENDORS, field_name="vendor")
        normalized = _require_str(normalized_key, field_name="normalized_key")
        existing = next(
            (
                row
                for row in self._mappings.values()
                if row.vendor == vendor_name and row.normalized_key == normalized
            ),
            None,
        )
        if existing:
            existing.vendor_field_key = _require_str(vendor_field_key, field_name="vendor_field_key")
            existing.required = required
            existing.transform = _optional_str(transform)
            existing.updated_at = now
            return deepcopy(existing)
        row = VendorFieldMapping(
            vendor=vendor_name,
            normalized_key=normalized,
            vendor_field_key=_require_str(vendor_field_key, field_name="vendor_field_key"),
            required=required,
            transform=_optional_str(transform),
            created_at=now,
            updated_at=now,
        )
        self._mappings[row.id] = row
        return deepcopy(row)

    def list_vendor_mappings(self, vendor: str | None = None) -> list[VendorFieldMapping]:
        rows = list(self._mappings.values())
        if vendor:
            wanted = _one_of(vendor, VENDORS, field_name="vendor")
            rows = [row for row in rows if row.vendor == wanted]
        return [deepcopy(row) for row in rows]

    def create_submit_request(
        self,
        user_id: str,
        auto_apply_id: str,
        *,
        vendor: str,
        idempotency_key: str,
        request_blob_uri: str | None = None,
    ) -> SubmitRequest:
        attempt = self._owned_attempt(auto_apply_id, user_id)
        vendor_name = _one_of(vendor, VENDORS, field_name="vendor")
        key = _require_str(idempotency_key, field_name="idempotency_key")
        for row in self._submits.values():
            if row.vendor == vendor_name and row.idempotency_key == key:
                raise AutoApplyConflictError("idempotency_key already used for this vendor")
        now = utc_now()
        row = SubmitRequest(
            auto_apply_id=attempt.id,
            user_id=user_id,
            vendor=vendor_name,
            status="queued",
            idempotency_key=key,
            request_blob_uri=_optional_str(request_blob_uri),
            created_at=now,
            updated_at=now,
        )
        self._submits[row.id] = row
        return deepcopy(row)

    def complete_submit(
        self,
        user_id: str,
        submit_id: str,
        *,
        status: str,
        vendor_application_id: str | None = None,
        vendor_request_id: str | None = None,
        response_blob_uri: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retry_count: int | None = None,
    ) -> SubmitRequest:
        row = self._submits.get(submit_id)
        if row is None or row.user_id != user_id:
            raise AutoApplyNotFoundError("submit request not found")
        wanted_status = _one_of(status, SUBMIT_STATUSES, field_name="status")
        app_id = _optional_str(vendor_application_id) or row.vendor_application_id
        if app_id:
            clash = next(
                (
                    other
                    for other in self._submits.values()
                    if other.id != row.id and other.vendor == row.vendor and other.vendor_application_id == app_id
                ),
                None,
            )
            if clash:
                raise AutoApplyConflictError("vendor_application_id already linked for this vendor")
        row.status = wanted_status
        row.vendor_application_id = app_id
        row.vendor_request_id = _optional_str(vendor_request_id) or row.vendor_request_id
        row.response_blob_uri = _optional_str(response_blob_uri) or row.response_blob_uri
        row.error_code = _optional_str(error_code)
        row.error_message = _optional_str(error_message)
        if retry_count is not None:
            row.retry_count = retry_count
        row.updated_at = utc_now()
        attempt = self._attempts[row.auto_apply_id]
        if row.status == "failed":
            attempt.last_error_code = row.error_code
            attempt.last_error_message = row.error_message
            if "failed" in ALLOWED_TRANSITIONS.get(attempt.status, frozenset()):
                attempt.status = "failed"
            attempt.updated_at = utc_now()
            self._event(attempt, "submission_failed", {"submit_id": row.id, "error_code": row.error_code})
        elif row.status == "succeeded":
            self._event(
                attempt,
                "submission_succeeded",
                {"submit_id": row.id, "vendor_application_id": row.vendor_application_id},
            )
        return deepcopy(row)

    def list_submits(self, user_id: str, auto_apply_id: str) -> list[SubmitRequest]:
        self._owned_attempt(auto_apply_id, user_id)
        rows = [row for row in self._submits.values() if row.auto_apply_id == auto_apply_id]
        return [deepcopy(row) for row in rows]

    def list_status_events(
        self,
        user_id: str,
        auto_apply_id: str,
        *,
        now: str | None = None,
        include_expired: bool = False,
    ) -> list[StatusEvent]:
        self._owned_attempt(auto_apply_id, user_id)
        cutoff = plus_days(-STATUS_EVENTS_RETENTION_DAYS, now=now)
        rows = [row for row in self._events.values() if row.auto_apply_id == auto_apply_id]
        if not include_expired:
            rows = [row for row in rows if row.created_ts >= cutoff]
        rows.sort(key=lambda row: row.created_ts)
        return [deepcopy(row) for row in rows]

    def ingest_webhook(
        self,
        *,
        vendor: str,
        vendor_application_id: str,
        event_type: str,
        dedupe_key: str,
        payload_blob_uri: str | None = None,
        auto_apply_id: str | None = None,
        user_id: str | None = None,
    ) -> WebhookCallback:
        vendor_name = _one_of(vendor, VENDORS, field_name="vendor")
        app_id = _require_str(vendor_application_id, field_name="vendor_application_id")
        key = _require_str(dedupe_key, field_name="dedupe_key")
        for row in self._webhooks.values():
            if row.dedupe_key == key:
                return deepcopy(row)
        now = utc_now()
        linked = _optional_str(auto_apply_id)
        if not linked:
            submit = next(
                (
                    row
                    for row in self._submits.values()
                    if row.vendor == vendor_name and row.vendor_application_id == app_id
                ),
                None,
            )
            if submit:
                linked = submit.auto_apply_id
                user_id = submit.user_id
        row = WebhookCallback(
            vendor=vendor_name,
            vendor_application_id=app_id,
            auto_apply_id=linked,
            user_id=_optional_str(user_id),
            dedupe_key=key,
            event_type=_require_str(event_type, field_name="event_type"),
            payload_blob_uri=_optional_str(payload_blob_uri),
            received_at=now,
            expires_at=plus_days(WEBHOOK_RETENTION_DAYS, now=now),
        )
        self._webhooks[row.id] = row
        if linked and linked in self._attempts:
            self._event(self._attempts[linked], "vendor_ack", {"webhook_id": row.id, "event_type": row.event_type})
        return deepcopy(row)

    def list_webhooks(self, *, vendor_application_id: str | None = None, now: str | None = None, include_expired: bool = False) -> list[WebhookCallback]:
        rows = list(self._webhooks.values())
        if vendor_application_id:
            rows = [row for row in rows if row.vendor_application_id == vendor_application_id]
        if not include_expired:
            rows = [row for row in rows if not is_expired(row.expires_at, now=now)]
        rows.sort(key=lambda row: row.received_at)
        return [deepcopy(row) for row in rows]
