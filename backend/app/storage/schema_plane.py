"""SQL-shaped Kanban tables mapped onto Cosmos containers.

The Database PRDs already name physical containers. This module adds the
extra catalogs the schema Kanban asked for (candidates, companies, …) and
the DAOs, enums, FTS helper, tenant isolation, and computed-field stamps
that SQL would have expressed as tables, indexes, and triggers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.auto_apply.constants import ATTEMPT_STATUSES

DAY = 86_400
PARSE_QUEUE_TTL = 7 * DAY
SCRAPE_QUEUE_TTL = 7 * DAY
OUTBOX_TTL = 14 * DAY
DELIVERY_TTL = 90 * DAY

PARSE_QUEUE_STATES: frozenset[str] = frozenset({"queued", "processing", "done", "failed"})
APPLICATION_STATUS: frozenset[str] = frozenset(ATTEMPT_STATUSES)
EMAIL_DIRECTION: frozenset[str] = frozenset({"inbound", "outbound"})
EMAIL_PROVIDER: frozenset[str] = frozenset({"microsoft_365", "gmail", "imap"})
OUTBOX_STATES: frozenset[str] = frozenset({"pending", "sending", "delivered", "failed"})
WEBHOOK_DELIVERY_STATES: frozenset[str] = frozenset({"pending", "retrying", "delivered", "failed"})

PHYSICAL_CONTAINERS: tuple[str, ...] = (
    "candidates",
    "companies",
    "recruiters",
    "recruiter_inboxes",
    "resume_parse_queue",
    "auto_apply_rules",
    "integration_outbox",
    "attachments",
    "oauth_credentials",
    "webhooks_outbound",
    "webhook_deliveries",
    "scrape_jobs_queue",
)

# Kanban / SQL names that this plane owns or aliases. Physical ids stay in
# ``app.storage.epic.KANBAN_CONTAINERS``.
TABLE_ALIASES: dict[str, str] = {
    "job_postings": "job_postings_canonical",
    "resumes": "resumes",
    "candidates": "candidates",
    "applications": "auto_apply_attempts",
    "application_status_history": "status_events",
    "recruiters": "recruiters",
    "companies": "companies",
    "email_threads": "email_threads",
    "email_messages": "email_messages",
    "resume_parsing_queue": "resume_parse_queue",
    "auto_apply_rules": "auto_apply_rules",
    "webhooks_outbox": "integration_outbox",
    "audit_logs": "event_log",
    "attachments": "attachments",
    "mail_threads": "email_threads",
    "mail_messages": "email_messages",
    "thread_participants": "email_recipients",
    "email_attachments": "email_attachments",
    "auto_apply_runs": "apply_runs",
    "auto_apply_run_items": "auto_apply_attempts",
    "application_events": "status_events",
    "matching_models": "model_registry",
    "match_records": "match_records",
    "match_evidence": "match_evidence",
    "scrape_jobs_queue": "scrape_jobs_queue",
    "rate_limits": "source_rate_limits",
    "oauth_credentials": "oauth_credentials",
    "webhooks_outbound": "webhooks_outbound",
    "webhook_deliveries": "webhook_deliveries",
    "recruiter_inboxes": "recruiter_inboxes",
}

TENANT_FIELDS: dict[str, tuple[str, ...]] = {
    "resumes": ("user_id", "userId"),
    "resume_versions": ("user_id", "userId"),
    "auto_apply_attempts": ("user_id", "userId"),
    "apply_runs": ("userId", "user_id"),
    "attachments": ("userId", "user_id"),
    "auto_apply_rules": ("userId", "user_id"),
    "resume_parse_queue": ("userId", "user_id"),
    "oauth_credentials": ("userId", "user_id"),
    "matches": ("user_id", "userId"),
    "match_records": ("userId", "user_id"),
}

PII_SECRET_DEFAULT = "dev-settings-token-key"


def _policy(*composites: list[dict[str, str]]) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": '/"_etag"/?'}],
    }
    if composites:
        policy["compositeIndexes"] = list(composites)
    return policy


def container_specs() -> list[dict[str, Any]]:
    """Physical containers the Database PRDs did not already provision."""
    return [
        {"id": "candidates", "partition_key": "/id", "indexing_policy": _policy([{"path": "/email", "order": "ascending"}])},
        {
            "id": "companies",
            "partition_key": "/id",
            "indexing_policy": _policy([{"path": "/domain", "order": "ascending"}]),
        },
        {
            "id": "recruiters",
            "partition_key": "/companyId",
            "indexing_policy": _policy(
                [
                    {"path": "/companyId", "order": "ascending"},
                    {"path": "/email", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "recruiter_inboxes",
            "partition_key": "/recruiterId",
            "indexing_policy": _policy(
                [
                    {"path": "/recruiterId", "order": "ascending"},
                    {"path": "/provider", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "resume_parse_queue",
            "partition_key": "/userId",
            "indexing_policy": _policy(
                [
                    {"path": "/userId", "order": "ascending"},
                    {"path": "/status", "order": "ascending"},
                    {"path": "/createdAt", "order": "descending"},
                ]
            ),
        },
        {
            "id": "auto_apply_rules",
            "partition_key": "/userId",
            "indexing_policy": _policy(
                [
                    {"path": "/userId", "order": "ascending"},
                    {"path": "/priority", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "integration_outbox",
            "partition_key": "/id",
            "indexing_policy": _policy(
                [
                    {"path": "/status", "order": "ascending"},
                    {"path": "/nextRetryAt", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "attachments",
            "partition_key": "/userId",
            "indexing_policy": _policy(
                [
                    {"path": "/userId", "order": "ascending"},
                    {"path": "/kind", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "oauth_credentials",
            "partition_key": "/userId",
            "indexing_policy": {
                "indexingMode": "consistent",
                "automatic": True,
                "includedPaths": [{"path": "/*"}],
                "excludedPaths": [
                    {"path": '/"_etag"/?'},
                    {"path": "/access_token/?"},
                    {"path": "/refresh_token/?"},
                    {"path": "/secret/?"},
                ],
                "compositeIndexes": [
                    [
                        {"path": "/userId", "order": "ascending"},
                        {"path": "/provider", "order": "ascending"},
                    ]
                ],
            },
        },
        {
            "id": "webhooks_outbound",
            "partition_key": "/id",
            "indexing_policy": _policy([{"path": "/event", "order": "ascending"}]),
        },
        {
            "id": "webhook_deliveries",
            "partition_key": "/webhookId",
            "indexing_policy": _policy(
                [
                    {"path": "/webhookId", "order": "ascending"},
                    {"path": "/nextRetryAt", "order": "ascending"},
                ]
            ),
        },
        {
            "id": "scrape_jobs_queue",
            "partition_key": "/source",
            "indexing_policy": _policy(
                [
                    {"path": "/source", "order": "ascending"},
                    {"path": "/scheduledAt", "order": "ascending"},
                ]
            ),
        },
    ]


class UniqueConstraintError(RuntimeError):
    """Logical unique key already exists (Cosmos unique keys are per partition)."""

    status_code = 409


class TenantIsolationError(PermissionError):
    """Row belongs to a different user partition."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid4())


def contains_search(haystack: str | None, needle: str | None) -> bool:
    """Python stand-in for Cosmos ``CONTAINS(..., true)`` — not fullTextPolicy."""
    if not needle:
        return True
    return str(needle).casefold() in str(haystack or "").casefold()


def fts_query(field: str) -> str:
    return f"SELECT * FROM c WHERE CONTAINS(c.{field}, @q, true)"


def stamp_computed(doc: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    """Trigger equivalent: timestamps, status rollup, denormalized counters."""
    stamp = now or _now()
    out = dict(doc)
    out.setdefault("created_at", stamp)
    out.setdefault("createdAt", out["created_at"])
    out["updated_at"] = stamp
    out["updatedAt"] = stamp
    history = out.get("status_history")
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict):
            out["status_rollup"] = last.get("status") or last.get("event_type")
    items = out.get("items")
    if isinstance(items, list):
        out["item_count"] = len(items)
    return out


def assert_enum(value: str, allowed: frozenset[str], *, field: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}")
    return value


def owner_of(row: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if row.get(field):
            return str(row[field])
    return None


def assert_tenant(container: str, row: dict[str, Any], user_id: str) -> None:
    fields = TENANT_FIELDS.get(container)
    if not fields:
        return
    owner = owner_of(row, fields)
    if owner is not None and owner != str(user_id):
        raise TenantIsolationError(f"{container} row {row.get('id')} is not owned by {user_id}")


class SchemaDAO:
    """CRUD for the extra schema-plane containers. Does not grow ``dao.py``."""

    def __init__(self, dal: Any, *, secret: str = PII_SECRET_DEFAULT) -> None:
        self._dal = dal
        self._secret = secret

    def _encrypt(self, container: str, row: dict[str, Any]) -> dict[str, Any]:
        from app.storage.pii import encrypt_fields

        return encrypt_fields(container, row, secret=self._secret)

    def _decrypt(self, container: str, row: dict[str, Any]) -> dict[str, Any]:
        from app.storage.pii import decrypt_fields

        return decrypt_fields(container, row, secret=self._secret)

    def _stamp(self, row: dict[str, Any]) -> dict[str, Any]:
        from app.storage.sprocs import apply_timestamps

        return apply_timestamps(stamp_computed(row))

    def ensure_containers(self, database: Any) -> list[str]:
        from app.storage.catalog import container_by_id, cosmos_create_kwargs
        from app.storage.epic import resolve_container

        created: list[str] = []
        for spec in container_specs():
            kwargs = cosmos_create_kwargs(container_by_id(spec["id"]))
            database.create_container_if_not_exists(**kwargs)
            created.append(spec["id"])
        for alias in ("job_postings", "applications", "audit_logs", "mail_threads", "match_records"):
            physical = resolve_container(alias)
            database.create_container_if_not_exists(**cosmos_create_kwargs(container_by_id(physical)))
            created.append(alias)
        return created

    def _find(self, container: str, field: str, value: Any, *, partition_key: Any | None = None) -> list[dict[str, Any]]:
        page = self._dal.query(
            container,
            f"SELECT * FROM c WHERE c.{field} = @value",
            parameters=[{"name": "@value", "value": value}],
            partition_key=partition_key,
            allow_cross_partition=partition_key is None,
            max_items=50,
        )
        return [row for row in page.items if str(row.get(field) or "") == str(value)]

    def assert_unique(
        self,
        container: str,
        field: str,
        value: Any,
        *,
        partition_key: Any | None = None,
        exclude_id: str | None = None,
    ) -> None:
        if value in (None, ""):
            return
        for row in self._find(container, field, value, partition_key=partition_key):
            if exclude_id and str(row.get("id")) == str(exclude_id):
                continue
            raise UniqueConstraintError(f"duplicate {container}.{field}={value}")

    def create_candidate(
        self,
        *,
        email: str,
        name: str,
        phone: str | None = None,
        links: dict[str, str] | None = None,
        preferences: dict[str, Any] | None = None,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        email_norm = email.strip().lower()
        from app.storage.pii import hash_text

        email_hash = hash_text(email_norm)
        self.assert_unique("candidates", "email_hash", email_hash)
        row = self._stamp(
            {
                "id": candidate_id or new_id(),
                "email": email_norm,
                "email_hash": email_hash,
                "phone": phone,
                "name": name,
                "links": links or {},
                "preferences": preferences or {},
                "is_deleted": False,
                "deleted_at": None,
            }
        )
        return self._dal.create("candidates", self._encrypt("candidates", row))

    def create_company(self, *, name: str, domain: str, company_id: str | None = None) -> dict[str, Any]:
        domain_norm = domain.strip().lower()
        self.assert_unique("companies", "domain", domain_norm)
        row = self._stamp(
            {
                "id": company_id or new_id(),
                "name": name,
                "domain": domain_norm,
                "is_deleted": False,
                "deleted_at": None,
            }
        )
        return self._dal.create("companies", row)

    def create_recruiter(
        self,
        *,
        company_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        channel: str = "email",
        recruiter_id: str | None = None,
    ) -> dict[str, Any]:
        email_norm = email.strip().lower()
        from app.storage.pii import hash_text

        email_hash = hash_text(email_norm)
        self.assert_unique("recruiters", "email_hash", email_hash, partition_key=company_id)
        row = self._stamp(
            {
                "id": recruiter_id or new_id(),
                "companyId": company_id,
                "name": name,
                "email": email_norm,
                "email_hash": email_hash,
                "phone": phone,
                "channel": channel,
                "is_deleted": False,
                "deleted_at": None,
            }
        )
        return self._dal.create("recruiters", self._encrypt("recruiters", row))

    def create_inbox(
        self,
        *,
        recruiter_id: str,
        provider: str,
        address: str,
        oauth_ref: str | None = None,
    ) -> dict[str, Any]:
        assert_enum(provider, EMAIL_PROVIDER, field="provider")
        row = self._stamp(
            {
                "id": new_id(),
                "recruiterId": recruiter_id,
                "provider": provider,
                "address": address.strip().lower(),
                "oauthRef": oauth_ref,
                "syncCursor": None,
            }
        )
        return self._dal.create("recruiter_inboxes", row)

    def enqueue_parse(
        self,
        user_id: str,
        resume_id: str,
        *,
        status: str = "queued",
    ) -> dict[str, Any]:
        assert_enum(status, PARSE_QUEUE_STATES, field="status")
        assert_tenant("resume_parse_queue", {"userId": user_id}, user_id)
        row = self._stamp(
            {
                "id": new_id(),
                "userId": user_id,
                "resumeId": resume_id,
                "status": status,
                "retries": 0,
                "error": None,
            }
        )
        return self._dal.create("resume_parse_queue", row)

    def transition_parse(self, user_id: str, item_id: str, status: str, *, error: str | None = None) -> dict[str, Any]:
        assert_enum(status, PARSE_QUEUE_STATES, field="status")
        row = self._dal.read("resume_parse_queue", item_id, partition_key=user_id)
        assert_tenant("resume_parse_queue", row, user_id)
        row["status"] = status
        if status == "failed":
            row["retries"] = int(row.get("retries") or 0) + 1
            row["error"] = error
        elif status == "done":
            row["error"] = None
        return self._dal.upsert("resume_parse_queue", stamp_computed(row))

    def upsert_rule(
        self,
        user_id: str,
        *,
        conditions: dict[str, Any],
        priority: int = 100,
        enabled: bool = True,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        row = self._stamp(
            {
                "id": rule_id or new_id(),
                "userId": user_id,
                "conditions": conditions,
                "priority": int(priority),
                "enabled": bool(enabled),
            }
        )
        assert_tenant("auto_apply_rules", row, user_id)
        return self._dal.upsert("auto_apply_rules", row)

    def enqueue_outbox(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        dedupe_key: str,
        next_retry_at: str | None = None,
    ) -> dict[str, Any]:
        existing = None
        try:
            existing = self._dal.read("integration_outbox", dedupe_key, partition_key=dedupe_key)
        except KeyError:
            existing = None
        if existing:
            return existing
        row = self._stamp(
            {
                "id": dedupe_key,
                "dedupe_key": dedupe_key,
                "eventType": event_type,
                "payload": payload,
                "status": "pending",
                "retries": 0,
                "nextRetryAt": next_retry_at or _now(),
            }
        )
        return self._dal.create("integration_outbox", row)

    def save_attachment(
        self,
        user_id: str,
        *,
        kind: str,
        filename: str,
        mime_type: str,
        size: int,
        blob_uri: str,
        checksum: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        if checksum:
            self.assert_unique("attachments", "checksum", checksum, partition_key=user_id)
        row = self._stamp(
            {
                "id": new_id(),
                "userId": user_id,
                "kind": kind,
                "filename": filename,
                "mimeType": mime_type,
                "size": int(size),
                "blobUri": blob_uri,
                "checksum": checksum,
                "parentId": parent_id,
                "is_deleted": False,
                "deleted_at": None,
            }
        )
        assert_tenant("attachments", row, user_id)
        return self._dal.create("attachments", row)

    def save_oauth(
        self,
        user_id: str,
        *,
        provider: str,
        access_token: str,
        refresh_token: str | None = None,
        scopes: list[str] | None = None,
        expires_at: str | None = None,
        account: str | None = None,
    ) -> dict[str, Any]:
        row = self._stamp(
            {
                "id": f"{user_id}:{provider}",
                "userId": user_id,
                "provider": provider,
                "account": account,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "scopes": scopes or [],
                "expires_at": expires_at,
            }
        )
        assert_tenant("oauth_credentials", row, user_id)
        return self._dal.upsert("oauth_credentials", self._encrypt("oauth_credentials", row))

    def read_oauth(self, user_id: str, provider: str) -> dict[str, Any]:
        row = self._dal.read("oauth_credentials", f"{user_id}:{provider}", partition_key=user_id)
        return self._decrypt("oauth_credentials", row)

    def register_webhook(self, *, event: str, target_url: str, secret: str, active: bool = True) -> dict[str, Any]:
        self.assert_unique("webhooks_outbound", "target_url", target_url)
        row = self._stamp(
            {
                "id": new_id(),
                "event": event,
                "target_url": target_url,
                "secret": secret,
                "active": active,
            }
        )
        return self._dal.create("webhooks_outbound", self._encrypt("webhooks_outbound", row))

    def record_delivery(
        self,
        webhook_id: str,
        *,
        payload_ref: str,
        status: str = "pending",
        response_code: int | None = None,
    ) -> dict[str, Any]:
        assert_enum(status, WEBHOOK_DELIVERY_STATES, field="status")
        row = self._stamp(
            {
                "id": new_id(),
                "webhookId": webhook_id,
                "payloadRef": payload_ref,
                "status": status,
                "responseCode": response_code,
                "retries": 0,
                "nextRetryAt": _now(),
            }
        )
        return self._dal.create("webhook_deliveries", row)

    def enqueue_scrape(
        self,
        *,
        source: str,
        url: str,
        fingerprint: str,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        self.assert_unique("scrape_jobs_queue", "fingerprint", fingerprint, partition_key=source)
        row = self._stamp(
            {
                "id": fingerprint,
                "source": source,
                "url": url,
                "fingerprint": fingerprint,
                "scheduledAt": scheduled_at or _now(),
                "attempts": 0,
                "status": "queued",
            }
        )
        return self._dal.create("scrape_jobs_queue", row)

    def search_text(
        self,
        container: str,
        field: str,
        query: str,
        *,
        partition_key: Any | None = None,
    ) -> list[dict[str, Any]]:
        page = self._dal.query(
            container,
            fts_query(field),
            parameters=[{"name": "@q", "value": query}],
            partition_key=partition_key,
            allow_cross_partition=partition_key is None,
            max_items=50,
        )
        return [row for row in page.items if contains_search(str(row.get(field) or ""), query)]

    def read_tenant(self, container: str, item_id: str, *, user_id: str, partition_key: Any | None = None) -> dict[str, Any]:
        row = self._dal.read(container, item_id, partition_key=partition_key if partition_key is not None else user_id)
        assert_tenant(container, row, user_id)
        return row
