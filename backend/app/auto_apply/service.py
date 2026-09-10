"""Auto-Apply application service (Backend PRD)."""

from __future__ import annotations

import json
from typing import Any, Callable
from uuid import uuid4

from app.auto_apply.blobs import AutoApplyBlobStore, InMemoryBlobStore
from app.auto_apply.constants import (
    POISON_DEQUEUE,
    REQUEST_QUEUE,
    SAS_TTL_MINUTES,
    VENDORS,
)
from app.auto_apply.cover import generate_cover_letter
from app.auto_apply.errors import AutoApplyConflictError, AutoApplyNotFoundError, AutoApplyValidationError
from app.auto_apply.models import AutoApplyAttempt
from app.auto_apply.package import build_manual_package_zip
from app.auto_apply.queues import InMemoryJobQueue, JobQueue
from app.auto_apply.store import AutoApplyStore, get_auto_apply_store
from app.auto_apply.submitters import HttpPoster, map_vendor_fields, submit_to_vendor
from app.config import get_settings

Clock = Callable[[], str]

PROFILE = {
    "full_name": "Alex Jobseeker",
    "email": "alex@example.com",
    "phone": "+15555550100",
    "name": "Alex Jobseeker",
}

STATE_MAP = {
    "draft": "created",
    "queued": "queued",
    "submitting": "submitting",
    "submitted": "submitted",
    "succeeded": "submitted",
    "failed": "failed",
    "needs_review": "packaged",
    "rate_limited": "rate_limited",
}


def _require_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AutoApplyValidationError(f"{field_name} is required", path=field_name)
    return value.strip()


def _vendor(job_source: Any) -> str:
    value = _require_str(job_source, field_name="job_source").lower()
    if value not in VENDORS:
        raise AutoApplyValidationError("job_source must be greenhouse, lever, or manual", path="job_source")
    return value


def _cover_mode(value: Any) -> str:
    mode = (value or "none")
    if not isinstance(mode, str):
        raise AutoApplyValidationError("cover_letter_mode is invalid", path="cover_letter_mode")
    cleaned = mode.strip().lower()
    if cleaned not in {"none", "upload", "generate"}:
        raise AutoApplyValidationError("cover_letter_mode must be none, upload, or generate", path="cover_letter_mode")
    return cleaned


def _needs_manual_package(vendor: str, posting_url: str | None) -> bool:
    if vendor == "manual":
        return True
    haystack = (posting_url or "").lower()
    return any(token in haystack for token in ("captcha", "sso", "unsupported", "manual"))


def _api_state(attempt: AutoApplyAttempt, *, cancelled: bool = False) -> str:
    if cancelled or attempt.last_error_code == "cancelled":
        return "cancelled"
    return STATE_MAP.get(attempt.status, attempt.status)


class AutoApplyService:
    def __init__(
        self,
        store: AutoApplyStore | None = None,
        queue: JobQueue | None = None,
        blobs: AutoApplyBlobStore | None = None,
        poster: HttpPoster | None = None,
    ) -> None:
        self.store = store or get_auto_apply_store()
        self.queue = queue or InMemoryJobQueue()
        self.blobs = blobs or InMemoryBlobStore()
        self.poster = poster
        self.processed = 0
        self.poisoned = 0
        try:
            self.store.seed_default_mappings()
        except Exception:
            pass

    def create_request(self, user_id: str, body: dict[str, Any], *, idempotency_key: str | None = None) -> tuple[int, dict[str, Any]]:
        vendor = _vendor(body.get("job_source") or body.get("vendor"))
        posting_url = body.get("posting_url")
        job_posting_id = body.get("job_posting_id") or body.get("job_id")
        if not posting_url and not job_posting_id:
            raise AutoApplyValidationError("job_posting_id or posting_url is required", path="job_posting_id")
        resume_id = body.get("resume_id") or body.get("resume_blob_ref") or "resume-active"
        cover_mode = _cover_mode(body.get("cover_letter_mode"))
        consent = bool(body.get("consent_approved") if "consent_approved" in body else True)
        if not consent:
            raise AutoApplyValidationError("consent_approved must be true", path="consent_approved")
        answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
        mode = "manual_package" if vendor == "manual" or _needs_manual_package(vendor, posting_url if isinstance(posting_url, str) else None) else "api"
        key = idempotency_key or (body.get("idempotency_key") if isinstance(body.get("idempotency_key"), str) else None)

        try:
            attempt = self.store.create_attempt(
                user_id,
                vendor=vendor,
                mode=mode,
                job_id=str(job_posting_id) if job_posting_id else None,
                source_application_id=str(job_posting_id) if job_posting_id else None,
                posting_url=str(posting_url) if posting_url else None,
                resume_id=str(resume_id),
            )
        except AutoApplyConflictError as exc:
            existing = self._in_flight(
                user_id,
                str(job_posting_id) if job_posting_id else None,
                str(posting_url) if posting_url else None,
            )
            raise AutoApplyConflictError(
                str(exc),
                request_id=existing.id if existing else getattr(exc, "request_id", None),
            ) from exc

        variant = self.store.create_resume_variant(
            user_id,
            label="Active resume",
            blob_uri=f"resumes/{user_id}/{resume_id}.pdf",
            resume_id=str(resume_id),
        )
        cover = None
        if cover_mode == "generate":
            letter = generate_cover_letter(attempt, PROFILE)
            cover_path = f"cover_letters/{user_id}/{attempt.id}.txt"
            self.blobs.put(cover_path, letter.encode("utf-8"))
            cover = self.store.create_cover_letter(
                user_id,
                source="ai",
                body_text=letter,
                blob_uri=cover_path,
                auto_apply_id=attempt.id,
            )
        elif cover_mode == "upload":
            blob_ref = body.get("cover_letter_blob_ref")
            uploaded = body.get("cover_letter_text")
            body_text = uploaded.strip() if isinstance(uploaded, str) and uploaded.strip() else None
            cover_path = str(blob_ref) if blob_ref else f"cover_letters/{user_id}/{attempt.id}.txt"
            if body_text:
                self.blobs.put(cover_path, body_text.encode("utf-8"))
            cover = self.store.create_cover_letter(
                user_id,
                source="upload",
                body_text=body_text,
                blob_uri=cover_path,
                auto_apply_id=attempt.id,
            )
        self._seed_autofill(user_id, attempt, vendor, answers)
        self.store.put_package(
            user_id,
            attempt.id,
            resume_variant_id=variant.id,
            cover_letter_id=cover.id if cover else None,
            filled_fields_json=dict(answers),
            deep_link_url=attempt.posting_url,
            package_blob_uri=f"packages/{user_id}/{attempt.id}.zip" if mode == "manual_package" else None,
        )
        self.store.approve(user_id, attempt.id)
        queued = self.store.queue(user_id, attempt.id)
        self.queue.enqueue(
            get_settings().auto_apply_request_queue or REQUEST_QUEUE,
            {
                "eventType": "AutoApplyQueued",
                "userId": user_id,
                "requestId": queued.id,
                "idempotencyKey": key,
            },
        )
        if isinstance(self.queue, InMemoryJobQueue):
            self.process_request({"eventType": "AutoApplyQueued", "userId": user_id, "requestId": queued.id})
        loaded = self.store.get_attempt(queued.id, user_id=user_id)
        return 201, {"request_id": loaded.id, "state": _api_state(loaded), "created_at": loaded.created_at}

    def get_request(self, user_id: str, request_id: str) -> dict[str, Any]:
        attempt = self.store.get_attempt(request_id, user_id=user_id)
        return self._detail(user_id, attempt)

    def list_requests(self, user_id: str, *, status: str | None = None) -> dict[str, Any]:
        wanted = None
        if status:
            reverse = {value: key for key, value in STATE_MAP.items()}
            wanted = reverse.get(status.strip().lower(), status.strip().lower())
        rows = self.store.list_attempts(user_id, status=wanted)
        return {"items": [self._summary(row) for row in rows]}

    def cancel(self, user_id: str, request_id: str) -> tuple[int, dict[str, Any]]:
        attempt = self.store.get_attempt(request_id, user_id=user_id)
        if attempt.status in {"submitting", "submitted", "succeeded"}:
            raise AutoApplyConflictError("cannot cancel after submission has started")
        if attempt.status in {"failed", "needs_review", "rate_limited"}:
            raise AutoApplyConflictError("request is already terminal")
        updated = self.store.transition(user_id, request_id, "failed", payload={"cancelled": True, "error_code": "cancelled"})
        stored = self.store._attempts[updated.id] if hasattr(self.store, "_attempts") else None
        if stored is not None:
            stored.last_error_code = "cancelled"
            stored.last_error_message = "Cancelled before submit"
        loaded = self.store.get_attempt(request_id, user_id=user_id)
        if loaded.last_error_code != "cancelled" and hasattr(self.store, "_attempts"):
            row = self.store._attempts[request_id]
            row.last_error_code = "cancelled"
            row.last_error_message = "Cancelled before submit"
            loaded = self.store.get_attempt(request_id, user_id=user_id)
        return 202, {"state": "cancelled", "request_id": loaded.id}

    def ingest_webhook(self, provider: str, body: dict[str, Any], *, secret: str | None) -> dict[str, Any]:
        settings = get_settings()
        expected = settings.auto_apply_webhook_secret
        if expected and secret != expected and (settings.auth_mode or "dev") != "dev":
            raise AutoApplyValidationError("invalid webhook secret", path="secret")
        vendor = _vendor(provider)
        app_id = _require_str(body.get("vendor_application_id") or body.get("application_id"), field_name="vendor_application_id")
        event_type = str(body.get("event_type") or body.get("type") or "vendor_ack")
        dedupe = str(body.get("dedupe_key") or f"{vendor}:{app_id}:{event_type}")
        row = self.store.ingest_webhook(
            vendor=vendor,
            vendor_application_id=app_id,
            event_type=event_type,
            dedupe_key=dedupe,
            payload_blob_uri=str(body.get("payload_blob_uri")) if body.get("payload_blob_uri") else None,
        )
        return {"id": row.id, "vendor_application_id": row.vendor_application_id, "auto_apply_id": row.auto_apply_id}

    def process_request(self, payload: dict[str, Any], *, dequeue_count: int = 1) -> None:
        settings = get_settings()
        limit = settings.auto_apply_poison_dequeue or POISON_DEQUEUE
        if dequeue_count > limit:
            self.poisoned += 1
            return
        if payload.get("eventType") != "AutoApplyQueued":
            raise AutoApplyValidationError("unsupported eventType")
        user_id = _require_str(payload.get("userId"), field_name="userId")
        request_id = _require_str(payload.get("requestId"), field_name="requestId")
        attempt = self.store.get_attempt(request_id, user_id=user_id)
        if attempt.status != "queued":
            return
        self.processed += 1
        if attempt.mode == "manual_package" or _needs_manual_package(attempt.vendor, attempt.posting_url):
            self._package_manual(user_id, attempt)
            return
        self._submit_programmatic(user_id, attempt)

    def _package_manual(self, user_id: str, attempt: AutoApplyAttempt) -> None:
        package_uri = f"packages/{user_id}/{attempt.id}.zip"
        cover_text = self._cover_text(user_id, attempt.id)
        fields = {row.field_key: row.value for row in self.store.list_autofill(user_id, attempt.id)}
        archive = build_manual_package_zip(
            deep_link=attempt.posting_url,
            resume_id=attempt.resume_id,
            cover_text=cover_text,
            fields=fields,
        )
        self.blobs.put(package_uri, archive)
        try:
            self.store.put_package(user_id, attempt.id, package_blob_uri=package_uri, deep_link_url=attempt.posting_url)
        except AutoApplyConflictError:
            pass
        self.store.lock_package(user_id, attempt.id)
        self.store.transition(user_id, attempt.id, "needs_review", payload={"reason": "manual_package"})

    def _submit_programmatic(self, user_id: str, attempt: AutoApplyAttempt) -> None:
        self.store.transition(user_id, attempt.id, "submitting")
        payload_uri = f"provider_payloads/{user_id}/{attempt.id}.json"
        submit = self.store.create_submit_request(
            user_id,
            attempt.id,
            vendor=attempt.vendor,
            idempotency_key=f"{attempt.id}:{attempt.vendor}",
            request_blob_uri=payload_uri,
        )
        mappings = self.store.list_vendor_mappings(attempt.vendor)
        fields = map_vendor_fields(
            attempt.vendor,
            profile=PROFILE,
            answers={},
            autofill=self.store.list_autofill(user_id, attempt.id),
            mappings=mappings,
        )
        cover_text = self._cover_text(user_id, attempt.id)
        if cover_text:
            fields["comments"] = cover_text
            fields["cover_letter"] = cover_text
        settings = get_settings()
        api_key = (
            settings.greenhouse_submit_api_key if attempt.vendor == "greenhouse" else settings.lever_submit_api_key
        )
        outcome = submit_to_vendor(
            attempt,
            fields,
            live=bool(settings.auto_apply_live_submit),
            api_key=api_key,
            poster=self.poster,
        )
        self.blobs.put(
            payload_uri,
            json.dumps({"endpoint": outcome.endpoint, "fields": outcome.fields, "status": outcome.status}).encode("utf-8"),
        )
        if outcome.status == "rate_limited":
            self.store.complete_submit(
                user_id,
                submit.id,
                status="retrying",
                error_code="rate_limited",
                error_message=outcome.error_message,
            )
            self.store.transition(user_id, attempt.id, "rate_limited")
            return
        if outcome.status != "succeeded":
            self.store.complete_submit(
                user_id,
                submit.id,
                status="failed",
                error_code=outcome.error_code,
                error_message=outcome.error_message,
            )
            return
        vendor_app = outcome.vendor_application_id or f"{attempt.vendor}-{attempt.id[:8]}"
        self.store.complete_submit(
            user_id,
            submit.id,
            status="succeeded",
            vendor_application_id=vendor_app,
            vendor_request_id=outcome.vendor_request_id or str(uuid4()),
        )
        self.store.transition(user_id, attempt.id, "submitted", payload={"vendor_application_id": vendor_app})
        self.store.transition(user_id, attempt.id, "succeeded", payload={"vendor_application_id": vendor_app})

    def _seed_autofill(self, user_id: str, attempt: AutoApplyAttempt, vendor: str, answers: dict[str, Any]) -> None:
        mappings = self.store.list_vendor_mappings(vendor)
        required_keys = [row.normalized_key for row in mappings if row.required] or ["full_name", "email"]
        for key in required_keys:
            value = answers.get(key) or answers.get(key.replace("_", "")) or PROFILE.get(key) or PROFILE.get("full_name")
            self.store.put_autofill(
                user_id,
                attempt.id,
                vendor=vendor if vendor != "manual" else "greenhouse",
                field_key=key,
                value=str(value),
                required=True,
                source="profile" if key in PROFILE else "user_input",
            )

    def _cover_text(self, user_id: str, attempt_id: str) -> str | None:
        try:
            package = self.store.get_package(attempt_id, user_id=user_id)
        except AutoApplyNotFoundError:
            return None
        if not package.cover_letter_id:
            return None
        try:
            cover = self.store.get_cover_letter(package.cover_letter_id, user_id=user_id)
        except AutoApplyNotFoundError:
            return None
        return cover.body_text

    def _in_flight(self, user_id: str, job_id: str | None, posting_url: str | None):
        for row in self.store.list_attempts(user_id):
            if row.status in {"succeeded", "failed"}:
                continue
            if job_id and row.source_application_id == job_id:
                return row
            if posting_url and row.posting_url == posting_url:
                return row
        return None

    def _summary(self, attempt: AutoApplyAttempt) -> dict[str, Any]:
        return {
            "request_id": attempt.id,
            "state": _api_state(attempt),
            "vendor": attempt.vendor,
            "mode": attempt.mode,
            "job_id": attempt.job_id,
            "posting_url": attempt.posting_url,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
            "failure_reason": attempt.last_error_message,
        }

    def _detail(self, user_id: str, attempt: AutoApplyAttempt) -> dict[str, Any]:
        settings = get_settings()
        minutes = settings.auto_apply_sas_minutes or SAS_TTL_MINUTES
        events = self.store.list_status_events(user_id, attempt.id)
        cancelled = any(event.payload.get("cancelled") for event in events)
        package = None
        try:
            package = self.store.get_package(attempt.id, user_id=user_id)
        except AutoApplyNotFoundError:
            package = None
        submits = self.store.list_submits(user_id, attempt.id)
        vendor_app = next((row.vendor_application_id for row in submits if row.vendor_application_id), None)
        autofill = [
            {"field_key": row.field_key, "value": row.value, "required": row.required, "source": row.source}
            for row in self.store.list_autofill(user_id, attempt.id)
        ]
        cover_text = None
        cover_source = None
        cover_blob = f"cover_letters/{user_id}/{attempt.id}.txt"
        if package and package.cover_letter_id:
            try:
                cover = self.store.get_cover_letter(package.cover_letter_id, user_id=user_id)
                cover_text = cover.body_text
                cover_source = cover.source
                cover_blob = cover.blob_uri or cover_blob
            except AutoApplyNotFoundError:
                cover_text = None
        return {
            "request_id": attempt.id,
            "state": _api_state(attempt, cancelled=cancelled),
            "state_history": [
                {"event": event.event_type, "at": event.created_ts, "payload": event.payload} for event in events
            ],
            "source": {
                "type": attempt.vendor,
                "job_posting_id": attempt.job_id,
                "posting_url": attempt.posting_url,
                "external_application_id": vendor_app,
            },
            "artifacts": {
                "resume_blob_sas": self.blobs.sas_url(f"resumes/{user_id}/{attempt.resume_id or 'resume'}.pdf", minutes=minutes),
                "cover_letter_blob_sas": self.blobs.sas_url(cover_blob, minutes=minutes)
                if package and package.cover_letter_id
                else None,
                "package_blob_sas": self.blobs.sas_url(package.package_blob_uri, minutes=minutes)
                if package and package.package_blob_uri
                else None,
                "deep_link_url": package.deep_link_url if package else attempt.posting_url,
            },
            "autofill": autofill,
            "cover_letter_text": cover_text,
            "cover_letter_source": cover_source,
            "validation_errors": None,
            "failure_reason": attempt.last_error_message,
            "submitted_at": next((event.created_ts for event in events if event.event_type == "submission_succeeded"), None),
            "packaged_at": next((event.created_ts for event in events if event.event_type == "needs_review"), None),
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
