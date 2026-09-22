"""Named domain DAOs wrapping CatalogRepository + MatchRecordStore.

Kanban titles map onto these classes. Feature stores stay the HTTP/runtime
path; DAOs are the Cosmos CRUD/idempotency/ETag contract used by seeds,
housekeeping, and smoke tests.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from app.dlq import enqueue as dlq_enqueue
from app.matching.keys import utc_now
from app.matching.records import MatchRecordStore
from app.pagination import normalize_limit, page_body
from app.storage.catalog import cosmos_create_kwargs, container_by_id, ensure_all_containers
from app.storage.dal import CosmosDAL
from app.storage.entity_dal import CatalogRepository, repository_for
from app.storage.epic import SETTINGS_DEFAULTS, settings_document
from app.storage.pii import hash_text, redact as redact_doc
from app.storage.schema_validate import validate_item
from app.storage.sprocs import apply_timestamps

MVP_CONTAINERS: tuple[str, ...] = (
    "users",
    "resumes",
    "resume_versions",
    "job_postings_canonical",
    "job_postings_raw",
    "source_fetch_runs",
    "source_rate_limits",
    "apply_runs",
    "auto_apply_attempts",
    "matches",
    "match_records",
    "match_evidence",
    "match_runs",
    "scoring_runs",
    "decision_events",
    "email_threads",
    "email_messages",
    "email_attachments",
    "user_settings",
    "source_toggles",
    "decision_log",
    "weight_config",
    "privacy_requests",
    "privacy_audit_log",
    "export_bundles",
)


def deterministic_id(*parts: str) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_run_id(*, user_id: str, job_id: str, resume_id: str, model_version: str = "") -> str:
    return deterministic_id(user_id, job_id, resume_id, model_version)


class DomainDAO:
    containers: tuple[str, ...] = ()

    def __init__(self, dal: CosmosDAL) -> None:
        self._dal = dal

    def repo(self, container: str) -> CatalogRepository:
        return repository_for(self._dal, container)

    def ensure(self, database: Any) -> list[str]:
        created: list[str] = []
        for name in self.containers:
            spec = container_by_id(name)
            database.create_container_if_not_exists(**cosmos_create_kwargs(spec))
            created.append(name)
        return created

    def _create(self, container: str, row: dict[str, Any]) -> dict[str, Any]:
        validate_item(container, row)
        return self.repo(container).create(apply_timestamps(row))

    def _upsert(self, container: str, row: dict[str, Any], *, etag: str | None = None) -> dict[str, Any]:
        validate_item(container, row)
        return self.repo(container).upsert(apply_timestamps(row), etag=etag)

    def _get(self, container: str, item_id: str, partition_key: Any) -> dict[str, Any]:
        return self.repo(container).get(item_id, partition_key=partition_key)

    def _page(self, container: str, partition_key: Any, *, cursor: str | None, limit: int | None) -> dict[str, Any]:
        size = normalize_limit(limit)
        page = self.repo(container).list_partition(partition_key, continuation=cursor, max_items=size)
        return page_body(list(page.items), next_cursor=page.continuation, extra={"requestCharge": page.request_charge})

    def record_error(self, *, kind: str, payload: dict[str, Any], replay_hint: str) -> dict[str, Any]:
        return dlq_enqueue(
            {
                "id": f"dlq-{kind}-{uuid4().hex[:8]}",
                "kind": kind,
                "replayHint": replay_hint,
                **payload,
            }
        )


class AutoApplyDAO(DomainDAO):
    containers = ("apply_runs", "auto_apply_attempts", "status_events", "cover_letters", "vendor_field_mappings")

    def ensure_auto_apply_containers(self, database: Any) -> list[str]:
        from app.auto_apply.containers import container_specs, ensure_auto_apply_containers as ensure_feature

        ensure_feature(database)
        created = [spec["id"] for spec in container_specs()]
        return created + ["apply_attempts", "form_field_mappings"]

    def create_apply_run(
        self,
        user_id: str,
        *,
        job_id: str = "",
        resume_id: str = "",
        model_version: str = "",
        method: str = "api",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        run_id = idempotency_key or apply_run_id(
            user_id=user_id, job_id=job_id, resume_id=resume_id, model_version=model_version
        )
        now = utc_now()
        row = {
            "id": run_id,
            "userId": user_id,
            "user_id": user_id,
            "jobId": job_id,
            "resumeId": resume_id,
            "modelVersion": model_version,
            "method": method,
            "status": "pending",
            "startedAt": now,
            "finishedAt": None,
            "errorCode": None,
            "errorMessage": None,
            "idempotency_key": run_id,
        }
        try:
            existing = self._get("apply_runs", run_id, user_id)
            return {"item": existing, "status": "existing"}
        except KeyError:
            try:
                created = self._create("apply_runs", row)
                return {"item": created, "status": "created"}
            except Exception:  # noqa: BLE001 — concurrent create is still idempotent
                existing = self._get("apply_runs", run_id, user_id)
                return {"item": existing, "status": "existing"}

    def append_attempt(self, user_id: str, run_id: str, **kwargs: Any) -> dict[str, Any]:
        job_id = str(kwargs.get("job_id") or kwargs.get("jobId") or "")
        resume_id = str(kwargs.get("resume_id") or kwargs.get("resumeId") or "")
        attempt_id = str(kwargs.get("id") or deterministic_id(user_id, run_id, job_id, resume_id))
        now = utc_now()
        row = {
            "id": attempt_id,
            "user_id": user_id,
            "userId": user_id,
            "run_id": run_id,
            "runId": run_id,
            "job_id": job_id,
            "jobId": job_id,
            "resume_id": resume_id,
            "step": kwargs.get("step") or "submit",
            "status": kwargs.get("status") or "draft",
            "details": kwargs.get("details") or {},
            "startedAt": now,
            "finishedAt": kwargs.get("finishedAt"),
            "vendor": kwargs.get("vendor") or "greenhouse",
        }
        try:
            return self._create("auto_apply_attempts", row)
        except Exception as exc:  # noqa: BLE001
            self.record_error(kind="apply", payload={"error": str(exc), "runId": run_id}, replay_hint=f"apply_runs/{run_id}")
            raise

    def set_run_status(self, user_id: str, run_id: str, status: str, *, etag: str | None = None) -> dict[str, Any]:
        current = self._get("apply_runs", run_id, user_id)
        current["status"] = status
        current["updatedAt"] = utc_now()
        if status in {"succeeded", "failed", "needs_manual"}:
            current["finishedAt"] = current["updatedAt"]
        return self._upsert("apply_runs", current, etag=etag or current.get("_etag"))

    def transition_run(
        self,
        user_id: str,
        run_id: str,
        status: str,
        *,
        etag: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        from app.auto_apply.constants import APPLY_RUN_TRANSITIONS

        current = self._get("apply_runs", run_id, user_id)
        current_status = str(current.get("status") or "pending")
        allowed = APPLY_RUN_TRANSITIONS.get(current_status, frozenset())
        if status not in allowed:
            raise ValueError(f"invalid apply-run transition {current_status!r} -> {status!r}")
        current["status"] = status
        current["updatedAt"] = utc_now()
        if error_code:
            current["errorCode"] = error_code
        if error_message:
            current["errorMessage"] = error_message
        if status in {"succeeded", "failed", "needs_manual"}:
            current["finishedAt"] = current["updatedAt"]
        return self._upsert("apply_runs", current, etag=etag or current.get("_etag"))

    def upsert_form_field_mapping(self, site_key: str, field: str, **kwargs: Any) -> dict[str, Any]:
        mapping_id = str(kwargs.get("id") or deterministic_id(site_key, field))
        row = {
            "id": mapping_id,
            "vendor": site_key,
            "siteKey": site_key,
            "selector": kwargs.get("selector") or f"[name={field}]",
            "field": field,
            "normalized_key": field,
            "required": bool(kwargs.get("required", True)),
            "transform": kwargs.get("transform") or "identity",
            "updatedAt": utc_now(),
        }
        if not row["selector"] or not row["field"]:
            raise ValueError("form_field_mappings require selector and field")
        return self._upsert("vendor_field_mappings", row, etag=kwargs.get("etag"))

    def list_form_field_mappings(self, site_key: str) -> list[dict[str, Any]]:
        page = self.repo("vendor_field_mappings").list_partition(site_key, max_items=100)
        return [row for row in page.items if str(row.get("siteKey") or row.get("vendor")) == site_key]

    def save_cover_letter(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        letter_id = str(kwargs.get("id") or uuid4())
        row = {
            "id": letter_id,
            "user_id": user_id,
            "userId": user_id,
            "jobId": kwargs.get("jobId") or kwargs.get("job_id") or "",
            "resumeId": kwargs.get("resumeId") or kwargs.get("resume_id") or "",
            "body": kwargs.get("body") or "",
            "model": kwargs.get("model") or "none",
            "source": kwargs.get("source") or "ai",
            "createdAt": utc_now(),
        }
        return self._create("cover_letters", row)

    def list_runs(self, user_id: str, *, cursor: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return self._page("apply_runs", user_id, cursor=cursor, limit=limit)


class ResumesDAO(DomainDAO):
    containers = ("resumes", "resume_versions", "resume_parse_events")

    def ensure_resumes_containers(self, database: Any) -> list[str]:
        from app.resumes.containers import ensure_resumes_containers as ensure_feature

        return ensure_feature(database)

    def create_resume(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        title = str(kwargs.get("title") or kwargs.get("original_filename") or "resume.pdf")
        resume_id = str(kwargs.get("id") or uuid4())
        now = utc_now()
        row = {
            "id": resume_id,
            "user_id": user_id,
            "userId": user_id,
            "title": title,
            "primaryFileId": kwargs.get("primaryFileId"),
            "parsedVersion": kwargs.get("parsedVersion"),
            "tags": list(kwargs.get("tags") or []),
            "original_filename": kwargs.get("original_filename") or title,
            "mime_type": kwargs.get("mime_type") or "application/pdf",
            "file_size": int(kwargs.get("file_size") or 0),
            "blob_uri": kwargs.get("blob_uri") or f"{user_id}/{resume_id}/resume.pdf",
            "checksum_sha256": kwargs.get("checksum_sha256") or "",
            "processing_status": "uploaded",
            "is_active": False,
            "is_deleted": False,
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            existing = self._get("resumes", resume_id, user_id)
            return existing
        except KeyError:
            return self._create("resumes", row)

    def list_user_resumes(self, user_id: str, *, cursor: str | None = None, limit: int | None = None) -> dict[str, Any]:
        page = self._page("resumes", user_id, cursor=cursor, limit=limit)
        items = [row for row in page["items"] if not row.get("is_deleted")]
        items.sort(key=lambda row: str(row.get("updatedAt") or row.get("updated_at") or ""), reverse=True)
        page["items"] = items
        return page

    def attach_file(self, user_id: str, resume_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.link_file(user_id, resume_id, **kwargs)

    def link_file(self, user_id: str, resume_id: str, **kwargs: Any) -> dict[str, Any]:
        version_id = str(kwargs.get("id") or uuid4())
        storage_path = str(kwargs.get("storagePath") or kwargs.get("blob_uri") or f"{user_id}/{resume_id}/{version_id}")
        row = {
            "id": version_id,
            "resume_id": resume_id,
            "resumeId": resume_id,
            "user_id": user_id,
            "userId": user_id,
            "blob_uri": storage_path,
            "storagePath": storage_path,
            "original_filename": kwargs.get("original_filename") or "resume.pdf",
            "mime_type": kwargs.get("mime_type") or kwargs.get("mimeType") or "application/pdf",
            "mimeType": kwargs.get("mimeType") or kwargs.get("mime_type") or "application/pdf",
            "file_size": int(kwargs.get("file_size") or kwargs.get("size") or 0),
            "size": int(kwargs.get("size") or kwargs.get("file_size") or 0),
            "checksum_sha256": kwargs.get("checksum_sha256") or kwargs.get("hash") or "",
            "hash": kwargs.get("hash") or kwargs.get("checksum_sha256") or "",
            "version": int(kwargs.get("version") or 1),
            "createdAt": utc_now(),
        }
        written = self._create("resume_versions", row)
        current = self._get("resumes", resume_id, user_id)
        current["primaryFileId"] = written["id"]
        current["updatedAt"] = utc_now()
        self._upsert("resumes", current, etag=kwargs.get("etag") or current.get("_etag"))
        return written

    def save_parsed_version(self, user_id: str, resume_id: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.save_version(user_id, resume_id, raw_json=snapshot or {})

    def save_version(self, user_id: str, resume_id: str, **kwargs: Any) -> dict[str, Any]:
        snapshot = dict(kwargs.get("raw_json") or kwargs.get("rawJson") or kwargs.get("snapshot") or {})
        version = int(kwargs.get("version") or 1)
        raw_json = kwargs.get("rawJson")
        hashed = raw_json if raw_json is not None else snapshot
        event = {
            "id": str(uuid4()),
            "resume_id": resume_id,
            "resumeId": resume_id,
            "user_id": user_id,
            "userId": user_id,
            "event_type": "succeeded",
            "version": version,
            "rawJsonHash": hash_text(json.dumps(hashed, sort_keys=True, default=str)) if hashed else "",
            "skills": list(kwargs.get("skills") or snapshot.get("skills") or []),
            "experience": list(kwargs.get("experience") or snapshot.get("experience") or []),
            "education": list(kwargs.get("education") or snapshot.get("education") or []),
            "snapshot": {key: snapshot[key] for key in ("skills", "experience", "education") if key in snapshot},
            "createdAt": utc_now(),
        }
        written = self.repo("resume_parse_events").create(apply_timestamps(event))
        current = self._get("resumes", resume_id, user_id)
        current["processing_status"] = "parsed"
        current["parsedVersion"] = version
        current["structured"] = event["snapshot"]
        current["updatedAt"] = utc_now()
        updated = self._upsert("resumes", current, etag=kwargs.get("etag") or current.get("_etag"))
        return {"resume": updated, "event": written}

    def set_active(self, user_id: str, resume_id: str) -> dict[str, Any]:
        listed = self.list(user_id)
        active = None
        for row in listed["items"]:
            flag = str(row.get("id")) == resume_id
            if bool(row.get("is_active")) == flag:
                if flag:
                    active = row
                continue
            row["is_active"] = flag
            saved = self._upsert("resumes", row, etag=row.get("_etag"))
            if flag:
                active = saved
        return active or self._get("resumes", resume_id, user_id)

    def list(self, user_id: str, *, cursor: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return self.list_user_resumes(user_id, cursor=cursor, limit=limit)


class JobIngestDAO(DomainDAO):
    containers = ("job_postings_canonical", "job_postings_raw", "source_fetch_runs", "source_rate_limits")

    def upsert_posting(self, **kwargs: Any) -> dict[str, Any]:
        canonical_key = str(kwargs.get("canonical_key") or "")
        posting_id = str(kwargs.get("id") or deterministic_id(canonical_key))
        row = {
            "id": posting_id,
            "canonical_key": canonical_key,
            "dedupe_hash": kwargs.get("dedupe_hash") or deterministic_id(canonical_key, "hash"),
            "title": kwargs.get("title") or "",
            "company": kwargs.get("company") or "",
            "location": kwargs.get("location") or "",
            "source": kwargs.get("source") or "greenhouse",
            "apply_url": kwargs.get("apply_url") or "",
            "is_active": True,
            "external_id": kwargs.get("external_id") or "",
        }
        existing = self.dedupe_by_external(canonical_key=canonical_key, external_id=str(row["external_id"]))
        if existing:
            row["id"] = existing["id"]
            return {"item": self._upsert("job_postings_canonical", {**existing, **row}), "status": "updated"}
        return {"item": self._create("job_postings_canonical", row), "status": "created"}

    def upsert_details(self, tenant_id: str, **kwargs: Any) -> dict[str, Any]:
        source_posting_id = str(kwargs.get("source_posting_id") or kwargs.get("external_id") or "")
        item_id = str(kwargs.get("id") or deterministic_id(tenant_id, source_posting_id))
        row = {
            "id": item_id,
            "source_tenant_id": tenant_id,
            "source_posting_id": source_posting_id,
            "payload_ref": kwargs.get("payload_ref") or "",
            "is_current": True,
        }
        return self._upsert("job_postings_raw", row)

    def dedupe_by_external(self, *, canonical_key: str = "", external_id: str = "") -> dict[str, Any] | None:
        page = self._dal.query(
            "job_postings_canonical",
            "SELECT * FROM c",
            max_items=100,
            allow_cross_partition=True,
        )
        for row in page.items:
            if canonical_key and str(row.get("canonical_key")) == canonical_key:
                return row
            if external_id and str(row.get("external_id")) == external_id:
                return row
        return None

    def log_ingest_run(self, tenant_id: str, **kwargs: Any) -> dict[str, Any]:
        run_id = str(kwargs.get("id") or uuid4())
        row = {
            "id": run_id,
            "source_tenant_id": tenant_id,
            "status": kwargs.get("status") or "running",
            "started_at": utc_now(),
            "error_summary": kwargs.get("error_summary"),
        }
        try:
            return self.repo("source_fetch_runs").create(apply_timestamps(row))
        except Exception as exc:  # noqa: BLE001
            self.record_error(
                kind="ingest",
                payload={"error": str(exc), "tenantId": tenant_id},
                replay_hint=f"source_fetch_runs/{run_id}",
            )
            raise

    def set_rate_limit(self, tenant_id: str, *, tokens: float, backoff_until: str | None = None) -> dict[str, Any]:
        row = {
            "id": tenant_id,
            "source_tenant_id": tenant_id,
            "tokens": float(tokens),
            "backoff_until": backoff_until,
        }
        return self.repo("source_rate_limits").upsert(apply_timestamps(row))

    def get_rate_limit(self, tenant_id: str) -> dict[str, Any]:
        return self._get("source_rate_limits", tenant_id, tenant_id)


class EmailDAO(DomainDAO):
    containers = ("email_threads", "email_messages", "email_attachments")

    def ensure_email_containers(self, database: Any) -> list[str]:
        from app.mail.containers import ensure_email_containers as ensure_feature

        return ensure_feature(database)

    def upsert_thread(self, account_id: str, user_id: str, **kwargs: Any) -> dict[str, Any]:
        thread_id = str(kwargs.get("id") or uuid4())
        now = utc_now()
        external = str(kwargs.get("externalThreadId") or kwargs.get("graph_conversation_id") or thread_id)
        row = {
            "id": thread_id,
            "email_account_id": account_id,
            "user_id": user_id,
            "userId": user_id,
            "subject": kwargs.get("subject") or "",
            "graph_conversation_id": external,
            "externalThreadId": external,
            "job_posting_id": kwargs.get("job_posting_id") or kwargs.get("jobId"),
            "application_id": kwargs.get("application_id") or kwargs.get("applicationId"),
            "firstSeenAt": kwargs.get("firstSeenAt") or now,
            "lastSeenAt": now,
        }
        return self._upsert("email_threads", row)

    def upsert_message(self, account_id: str, thread_id: str, **kwargs: Any) -> dict[str, Any]:
        message_id = str(kwargs.get("id") or uuid4())
        raw_body = str(kwargs.get("body_text") or kwargs.get("body") or "")
        from_addr = str(kwargs.get("from_address") or kwargs.get("from") or "")
        to_addrs = list(kwargs.get("to_addresses") or kwargs.get("to") or [])
        now = utc_now()
        row = {
            "id": message_id,
            "email_account_id": account_id,
            "email_thread_id": thread_id,
            "threadId": thread_id,
            "userId": kwargs.get("userId") or "",
            "from_address": from_addr,
            "from": from_addr,
            "to_addresses": to_addrs,
            "to": to_addrs,
            "subject": kwargs.get("subject") or "",
            "body_text": "",
            "bodyHash": hash_text(raw_body),
            "body_hash": hash_text(raw_body),
            "graph_message_id": kwargs.get("graph_message_id") or kwargs.get("externalMessageId") or message_id,
            "externalMessageId": kwargs.get("externalMessageId") or kwargs.get("graph_message_id") or message_id,
            "receivedAt": kwargs.get("receivedAt") or now,
            "isOutbound": bool(kwargs.get("isOutbound", False)),
            "createdAt": now,
        }
        return self._upsert("email_messages", row)

    def add_attachment_meta(self, account_id: str, message_id: str, **kwargs: Any) -> dict[str, Any]:
        row = {
            "id": str(kwargs.get("id") or uuid4()),
            "email_account_id": account_id,
            "userId": kwargs.get("userId") or "",
            "message_id": message_id,
            "messageId": message_id,
            "filename": kwargs.get("filename") or "file.bin",
            "mime_type": kwargs.get("mime_type") or kwargs.get("contentType") or "application/octet-stream",
            "contentType": kwargs.get("contentType") or kwargs.get("mime_type") or "application/octet-stream",
            "size_bytes": int(kwargs.get("size_bytes") or kwargs.get("size") or 0),
            "size": int(kwargs.get("size") or kwargs.get("size_bytes") or 0),
            "blob_uri": kwargs.get("blob_uri") or kwargs.get("storagePath") or "",
            "storagePath": kwargs.get("storagePath") or kwargs.get("blob_uri") or "",
        }
        return self._create("email_attachments", row)

    def list_thread_messages(
        self,
        account_id: str,
        thread_id: str,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        redact: bool = True,
    ) -> dict[str, Any]:
        page = self._page("email_messages", account_id, cursor=cursor, limit=limit)
        items = [row for row in page["items"] if str(row.get("email_thread_id")) == thread_id]
        if redact:
            items = [redact_doc("email_messages", row) for row in items]
        page["items"] = items
        return page


class SettingsDAO(DomainDAO):
    containers = ("user_settings", "source_toggles")

    def ensure_settings_containers(self, database: Any) -> list[str]:
        from app.settings.containers import container_specs, ensure_settings_containers as ensure_feature

        ensure_feature(database)
        return [spec["id"] for spec in container_specs()]

    def get_settings(self, user_id: str) -> dict[str, Any]:
        try:
            return self._get("user_settings", user_id, user_id)
        except KeyError:
            return self._create("user_settings", settings_document(user_id))

    def update_settings(self, user_id: str, patch: dict[str, Any], *, etag: str | None = None) -> dict[str, Any]:
        current = self.get_settings(user_id)
        current.update(patch)
        current["id"] = user_id
        current["user_id"] = user_id
        current["userId"] = user_id
        if "matchThreshold" in patch:
            current["match_threshold"] = int(patch["matchThreshold"])
        if "match_threshold" in patch:
            current["matchThreshold"] = int(patch["match_threshold"])
        current.setdefault("matchThreshold", current.get("match_threshold"))
        current.setdefault("timezone", patch.get("timezone") or current.get("timezone") or "UTC")
        if "quietHoursStart" in patch or "quietHoursEnd" in patch or "quiet_hours" in patch:
            current["quietHoursStart"] = patch.get("quietHoursStart") or current.get("quietHoursStart")
            current["quietHoursEnd"] = patch.get("quietHoursEnd") or current.get("quietHoursEnd")
            current["quiet_hours"] = patch.get("quiet_hours") or {
                "start": current.get("quietHoursStart"),
                "end": current.get("quietHoursEnd"),
            }
        current["updatedAt"] = utc_now()
        return self._upsert("user_settings", current, etag=etag or current.get("_etag"))

    def get_source_toggles(self, user_id: str) -> dict[str, Any]:
        try:
            return self._get("source_toggles", user_id, user_id)
        except KeyError:
            defaults = SETTINGS_DEFAULTS["sourceToggles"]
            now = utc_now()
            return self._create(
                "source_toggles",
                {
                    "id": user_id,
                    "userId": user_id,
                    "greenhouse": defaults["greenhouse"],
                    "lever": defaults["lever"],
                    "autoApply": defaults["autoApply"],
                    "sources": [
                        {"source": "greenhouse", "isEnabled": defaults["greenhouse"]},
                        {"source": "lever", "isEnabled": defaults["lever"]},
                    ],
                    "createdAt": now,
                    "updatedAt": now,
                },
            )

    def update_source_toggles(self, user_id: str, patch: dict[str, Any], *, etag: str | None = None) -> dict[str, Any]:
        current = self.get_source_toggles(user_id)
        for key in ("greenhouse", "lever", "autoApply"):
            if key in patch:
                current[key] = bool(patch[key])
        if "source" in patch:
            current["source"] = patch["source"]
            current["isEnabled"] = bool(patch.get("isEnabled", True))
            sources = list(current.get("sources") or [])
            updated = False
            for row in sources:
                if row.get("source") == patch["source"]:
                    row["isEnabled"] = current["isEnabled"]
                    updated = True
            if not updated:
                sources.append({"source": patch["source"], "isEnabled": current["isEnabled"]})
            current["sources"] = sources
        current["updatedAt"] = utc_now()
        return self._upsert("source_toggles", current, etag=etag or current.get("_etag"))


class LearningDAO(DomainDAO):
    containers = ("decision_log", "weight_config")

    def log_decision_feedback(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        rec_id = str(kwargs.get("recommendation_id") or kwargs.get("match_id") or uuid4())
        row = {
            "id": str(kwargs.get("id") or deterministic_id(user_id, rec_id)),
            "user_id": user_id,
            "recommendation_id": rec_id,
            "match_id": kwargs.get("match_id") or "",
            "decision": kwargs.get("decision") or "approve",
            "score": float(kwargs.get("score") or 0),
            "decided_at": utc_now(),
        }
        try:
            existing = self._get("decision_log", row["id"], user_id)
            return existing
        except KeyError:
            return self._create("decision_log", row)

    def upsert_model_weight_overrides(self, config_id: str, weights: dict[str, float], *, is_active: bool = True) -> dict[str, Any]:
        row = {
            "id": config_id,
            "weight_config_id": config_id,
            "weights": dict(weights),
            "is_active": is_active,
        }
        return self.repo("weight_config").upsert(apply_timestamps(row))


class PrivacyDAO(DomainDAO):
    containers = ("privacy_requests", "privacy_audit_log", "export_bundles")

    def create_export_request(self, user_id: str, *, note: str = "") -> dict[str, Any]:
        return self._open_request(user_id, kind="export", note=note)

    def create_deletion_request(self, user_id: str, *, note: str = "") -> dict[str, Any]:
        return self._open_request(user_id, kind="delete", note=note)

    def _open_request(self, user_id: str, *, kind: str, note: str) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "userId": user_id,
            "user_id": user_id,
            "kind": kind,
            "status": "open",
            "note": note,
            "createdAt": utc_now(),
        }
        created = self._create("privacy_requests", row)
        self.log_audit(user_id, action=f"{kind}_requested", request_id=created["id"])
        return created

    def log_audit(self, user_id: str, *, action: str, request_id: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "userId": user_id,
            "user_id": user_id,
            "action": action,
            "requestId": request_id,
            "occurredAt": utc_now(),
            **(extra or {}),
        }
        return self.repo("privacy_audit_log").create(apply_timestamps(row))

    def log_redaction(self, user_id: str, *, field: str, container: str) -> dict[str, Any]:
        return self.log_audit(user_id, action="redact", extra={"field": field, "container": container})

    def list_requests(self, user_id: str, *, cursor: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return self._page("privacy_requests", user_id, cursor=cursor, limit=limit)


class MatchingDAO(DomainDAO):
    containers = ("match_records", "match_evidence", "match_runs", "scoring_runs")

    def __init__(self, dal: CosmosDAL) -> None:
        super().__init__(dal)
        self.records = MatchRecordStore(dal)

    def ensure_matching_containers(self, database: Any) -> list[str]:
        from app.matching.containers import container_specs, ensure_matching_containers as ensure_feature

        ensure_feature(database)
        return [spec["id"] for spec in container_specs()]

    def create_match_record(
        self,
        user_id: str,
        *,
        job_id: str,
        resume_id: str,
        score: float,
        model_version: str = "matching-v1",
        evidence: list[str] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        saved = self.records.upsert_score(
            user_id=user_id,
            job_id=job_id,
            resume_id=resume_id,
            model_version=model_version,
            score=score,
            evidence=evidence,
            etag=etag,
        )
        saved["record"]["schemaVersion"] = saved["record"].get("schemaVersion") or 1
        return saved

    def get(self, user_id: str, match_id: str) -> dict[str, Any]:
        return self.records.get(user_id, match_id)

    def get_match_with_evidence(self, user_id: str, match_id: str) -> dict[str, Any]:
        return self.records.get_match_with_evidence(user_id, match_id)

    def list_records(self, user_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self.records.list_records(user_id, **kwargs)

    def list_matches(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.records.list_matches(user_id, **kwargs)

    def put_evidence_batch(self, user_id: str, match_id: str, sentences: list[str]) -> dict[str, Any]:
        return self.records.put_evidence(user_id=user_id, match_id=match_id, sentences=sentences)

    def upsert_evidence_batch(self, user_id: str, match_id: str, items: list[dict[str, Any]], *, ttl_seconds: int | None = None) -> dict[str, Any]:
        return self.records.upsert_evidence_batch(user_id, match_id, items, ttl_seconds=ttl_seconds)

    def create_scoring_run(self, user_id: str, *, resume_id: str, job_id: str, model_version: str = "matching-v1") -> dict[str, Any]:
        key = deterministic_id(user_id, resume_id, job_id, model_version)
        row = {
            "id": key,
            "user_id": user_id,
            "resume_id": resume_id,
            "job_id": job_id,
            "model_version_id": model_version,
            "idempotency_key": key,
            "status": "queued",
        }
        try:
            existing = self._get("match_runs", key, user_id)
            return {"item": existing, "status": "existing"}
        except KeyError:
            return {"item": self.repo("match_runs").create(apply_timestamps(row)), "status": "created"}

    def begin_scoring_run(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.records.begin_scoring_run(user_id, **kwargs)

    def end_scoring_run(self, user_id: str, correlation_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.records.end_scoring_run(user_id, correlation_id, **kwargs)

    def prune_retention(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.records.prune(user_id, **kwargs)

    def backfill_rescore(self, user_id: str, pairs: list[dict[str, Any]], *, model_version: str = "matching-v1") -> dict[str, Any]:
        return self.records.batch_rescore(user_id, pairs, model_version=model_version)

    def scoring_metrics(self) -> list[dict[str, Any]]:
        return list(self.records.telemetry)


class ReviewDAO(DomainDAO):
    containers = ("matches", "decision_events", "audit_events")

    def ensure_review_containers(self, database: Any) -> list[str]:
        from app.review.containers import ensure_review_containers as ensure_feature

        ensure_feature(database)
        from app.review.containers import container_specs

        return [spec["id"] for spec in container_specs()] + ["review_queue", "review_decisions"]

    def enqueue(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.enqueue_review_item(user_id, **kwargs)

    def enqueue_review_item(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        from datetime import datetime, timedelta, timezone

        from app.review.constants import QUEUE_TTL_SECONDS

        job_id = str(kwargs.get("job_id") or kwargs.get("jobId") or "")
        resume_id = str(kwargs.get("resume_id") or kwargs.get("resumeId") or "")
        match_id = str(kwargs.get("id") or deterministic_id(user_id, job_id, resume_id, str(kwargs.get("source") or "ai")))
        dup = self.dedupe(user_id, job_id=job_id, resume_id=resume_id)
        if dup:
            return {"item": dup, "status": "existing"}
        ttl = int(kwargs.get("ttl_seconds") or QUEUE_TTL_SECONDS)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        now = utc_now()
        row = {
            "id": match_id,
            "user_id": user_id,
            "userId": user_id,
            "job_id": job_id,
            "jobId": job_id,
            "resume_id": resume_id,
            "resumeId": resume_id,
            "status": "PENDING",
            "queueStatus": "queued",
            "source": kwargs.get("source") or "ai",
            "job_title": kwargs.get("job_title") or "",
            "company": kwargs.get("company") or "",
            "ai_score": float(kwargs.get("ai_score") or 0),
            "queued_at": now,
            "queuedAt": now,
            "expiresAt": expires.isoformat().replace("+00:00", "Z"),
            "ttl": ttl,
        }
        return {"item": self._create("matches", row), "status": "created"}

    def list_queue(
        self,
        user_id: str,
        status: str | None = "PENDING",
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        page = self._page("matches", user_id, cursor=cursor, limit=limit)
        items = list(page["items"])
        items.sort(key=lambda row: str(row.get("queued_at") or row.get("queuedAt") or ""), reverse=True)
        if status:
            items = [row for row in items if str(row.get("status")) == status]
        page["items"] = items
        return page

    def save_decision(
        self,
        user_id: str,
        match_id: str | None = None,
        decision: str = "approve",
        *,
        job_id: str | None = None,
        resume_id: str | None = None,
        reason: str = "",
        etag: str | None = None,
    ) -> dict[str, Any]:
        if not match_id and job_id and resume_id:
            found = self.dedupe(user_id, job_id=job_id, resume_id=resume_id)
            if not found:
                raise KeyError("queue item not found")
            match_id = str(found["id"])
            etag = etag or found.get("_etag")
        if not match_id:
            raise KeyError("match_id or job_id+resume_id required")
        match = self._get("matches", match_id, user_id)
        match["status"] = "APPROVED" if decision == "approve" else "REJECTED"
        match["latest_decision"] = decision
        match["reason"] = reason
        saved = self._upsert("matches", match, etag=etag or match.get("_etag"))
        event = {
            "id": str(uuid4()),
            "user_id": user_id,
            "userId": user_id,
            "match_id": match_id,
            "job_id": match.get("job_id") or job_id,
            "jobId": match.get("jobId") or match.get("job_id") or job_id,
            "resume_id": match.get("resume_id") or resume_id,
            "resumeId": match.get("resumeId") or match.get("resume_id") or resume_id,
            "decision": decision,
            "reason": reason,
            "decided_at": utc_now(),
            "createdAt": utc_now(),
        }
        written = self._create("decision_events", event)
        audit = self.repo("audit_events").create(
            apply_timestamps(
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "match_id": match_id,
                    "event_type": "DECISION_RECORDED",
                    "occurred_at": utc_now(),
                    "payload": {"decision": decision, "reasonHash": deterministic_id(reason) if reason else ""},
                }
            )
        )
        feedback = None
        try:
            feedback = LearningDAO(self._dal).log_decision_feedback(
                user_id,
                match_id=match_id,
                recommendation_id=match_id,
                decision=decision,
                score=float(match.get("ai_score") or 0),
            )
        except Exception:  # noqa: BLE001
            feedback = None
        return {"match": saved, "decision": written, "audit": audit, "feedback": feedback}

    def list_review_history(
        self,
        user_id: str,
        *,
        job_id: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        page = self._page("decision_events", user_id, cursor=cursor, limit=limit)
        items = list(page["items"])
        if job_id:
            items = [row for row in items if str(row.get("job_id") or row.get("jobId")) == job_id]
        items.sort(key=lambda row: str(row.get("createdAt") or row.get("created_at") or row.get("decided_at") or ""), reverse=True)
        page["items"] = items
        return page

    def expire_queue(self, user_id: str, *, now: str | None = None) -> dict[str, Any]:
        clock = now or utc_now()
        page = self.repo("matches").list_partition(user_id, max_items=100)
        expired_ids: list[str] = []
        for row in page.items:
            if str(row.get("status")) != "PENDING":
                continue
            expires = str(row.get("expiresAt") or row.get("expires_at") or "")
            if not expires or expires > clock:
                continue
            row["status"] = "REJECTED"
            row["expired"] = True
            row["queueStatus"] = "expired"
            row["latest_decision"] = "expired"
            self._upsert("matches", row, etag=row.get("_etag"))
            expired_ids.append(str(row["id"]))
        return {"expired": expired_ids, "count": len(expired_ids)}

    def dedupe(self, user_id: str, *, job_id: str, resume_id: str = "") -> dict[str, Any] | None:
        page = self.repo("matches").list_partition(user_id, max_items=100)
        for row in page.items:
            if str(row.get("job_id") or row.get("jobId")) == job_id:
                return row
        return None


def domain_daos(dal: CosmosDAL) -> dict[str, DomainDAO]:
    return {
        "auto_apply": AutoApplyDAO(dal),
        "resumes": ResumesDAO(dal),
        "job_ingest": JobIngestDAO(dal),
        "email": EmailDAO(dal),
        "settings": SettingsDAO(dal),
        "learning": LearningDAO(dal),
        "privacy": PrivacyDAO(dal),
        "matching": MatchingDAO(dal),
        "review": ReviewDAO(dal),
    }


def ensure_mvp_containers(database: Any) -> list[str]:
    created = ensure_all_containers(database)
    missing = [name for name in MVP_CONTAINERS if name not in created]
    if missing:
        raise RuntimeError(f"MVP containers missing from catalog: {missing}")
    return created


def seed_dao_defaults(dal: CosmosDAL, user_id: str = "seed-user-001") -> dict[str, Any]:
    settings = SettingsDAO(dal)
    learning = LearningDAO(dal)
    toggles = settings.get_source_toggles(user_id)
    prefs = settings.get_settings(user_id)
    weights = learning.upsert_model_weight_overrides(
        "weight-global-v1",
        {"keyword": 0.4, "semantic": 0.6},
        is_active=True,
    )
    return {
        "settings": prefs,
        "sourceToggles": toggles,
        "weightConfig": weights,
        "caps": {"matchThreshold": SETTINGS_DEFAULTS["matchThreshold"], "pageSize": 25},
    }
