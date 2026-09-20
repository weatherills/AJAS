"""Unified Cosmos container catalog for every Database PRD.

Each feature already ships `container_specs()`. This module is the single
place that adds partition-key rationale, unique-key policies, TTL, RU notes,
and the platform `users` / `event_log` containers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

DAY = 86_400

DEFAULT_INDEXING: dict[str, Any] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [{"path": '/"_etag"/?'}],
}


def _policy(*composites: list[dict[str, str]], extra_excluded: tuple[str, ...] = ()) -> dict[str, Any]:
    excluded = [{"path": '/"_etag"/?'}]
    excluded.extend({"path": path} for path in extra_excluded)
    policy: dict[str, Any] = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": excluded,
    }
    if composites:
        policy["compositeIndexes"] = list(composites)
    return policy


@dataclass(frozen=True)
class ContainerSpec:
    id: str
    feature: str
    entity: str
    partition_key: str
    indexing_policy: dict[str, Any]
    unique_keys: tuple[tuple[str, ...], ...] = ()
    logical_unique: tuple[str, ...] = ()
    default_ttl: int | None = None
    query_patterns: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    ru_note: str = ""

    def unique_key_policy(self) -> dict[str, Any] | None:
        if not self.unique_keys:
            return None
        return {"uniqueKeys": [{"paths": list(paths)} for paths in self.unique_keys]}


@dataclass(frozen=True)
class _Overlay:
    feature: str
    entity: str
    unique_keys: tuple[tuple[str, ...], ...] = ()
    logical_unique: tuple[str, ...] = ()
    default_ttl: int | None = None
    query_patterns: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    ru_note: str = ""
    indexing_policy: dict[str, Any] | None = None


# Unique-key paths omit the partition key (Cosmos unique keys are per partition
# and must not include the PK path).
_OVERLAYS: dict[str, _Overlay] = {
    "users": _Overlay(
        feature="platform",
        entity="User",
        logical_unique=("id", "email"),
        query_patterns=("point read by id",),
        relationships=("root for all user-scoped containers",),
        ru_note="PK /id so point reads ~1 RU. Email uniqueness is enforced in the DAL (PK is not /email).",
    ),
    "schema_migrations": _Overlay(
        feature="platform",
        entity="SchemaMigration",
        logical_unique=("id",),
        query_patterns=("point read by version id",),
        ru_note="Tiny catalog of applied schema versions; one row per version.",
    ),
    "event_log": _Overlay(
        feature="platform",
        entity="EventLog",
        default_ttl=30 * DAY,
        query_patterns=("user_id + occurred_at desc", "event_type filter"),
        relationships=("append-only; GDPR writes a delete receipt here",),
        ru_note="Append + recent-page queries. Composite keeps 25-item pages under ~5 RU.",
        indexing_policy=_policy(
            [
                {"path": "/user_id", "order": "ascending"},
                {"path": "/occurred_at", "order": "descending"},
            ],
            [
                {"path": "/user_id", "order": "ascending"},
                {"path": "/event_type", "order": "ascending"},
                {"path": "/occurred_at", "order": "descending"},
            ],
        ),
    ),
    "matches": _Overlay(
        feature="review",
        entity="ReviewMatch",
        unique_keys=(("/job_id", "/resume_id"),),
        logical_unique=("user_id", "job_id", "resume_id", "source"),
        query_patterns=("PENDING queue by user_id, status, queued_at", "ai_score range", "title/company/location filters"),
        relationships=("1—N decision_events; latest_decision_id FK",),
        ru_note="Queue page of 25 with status+queued_at composite ~3–5 RU. Cross-partition list is forbidden.",
    ),
    "decision_events": _Overlay(
        feature="review",
        entity="DecisionEvent",
        query_patterns=("match_id + decided_at desc",),
        relationships=("N—1 matches; append-only",),
        ru_note="History reads stay in the user partition; cheap in-partition queries.",
    ),
    "audit_events": _Overlay(
        feature="review",
        entity="AuditEvent",
        query_patterns=("match_id + occurred_at", "event_type + occurred_at"),
        relationships=("N—1 matches; UNLOCK_EXPIRED / degraded-view events",),
        ru_note="Telemetry volume is higher; composite indexes avoid scans on event_type.",
    ),
    "match_runs": _Overlay(
        feature="matching",
        entity="MatchRun",
        unique_keys=(("/idempotency_key",),),
        logical_unique=("user_id", "resume_id", "job_id", "idempotency_key"),
        query_patterns=("user+job", "user+resume", "meets_threshold + completed_at"),
        relationships=("1—1 match_explanations; N—1 model_registry",),
        ru_note="Idempotency unique key is a 1-RU conflict check on retry. Retain 18 months via purge, not TTL.",
    ),
    "match_explanations": _Overlay(
        feature="matching",
        entity="MatchExplanation",
        query_patterns=("point read by match_id partition",),
        relationships=("1—1 match_runs; overflow in Blob",),
        ru_note="PK is match_id so detail pane is a single-partition point read.",
    ),
    "user_match_prefs": _Overlay(
        feature="matching",
        entity="UserMatchPrefs",
        logical_unique=("user_id",),
        query_patterns=("point read by user_id",),
        relationships=("1—N user_match_pref_history",),
        ru_note="One document per user; always a point read (~1 RU).",
    ),
    "user_match_pref_history": _Overlay(
        feature="matching",
        entity="UserMatchPrefHistory",
        query_patterns=("user_id + created_at desc",),
        relationships=("append-only audit of prefs",),
        ru_note="Append-only; cheap in-partition history.",
    ),
    "model_registry": _Overlay(
        feature="matching",
        entity="ModelRegistry",
        logical_unique=("id", "ai_service+scorer_model+version+formula"),
        query_patterns=("lookup model_version_id", "composite scorer identity"),
        ru_note="Tiny catalog; full scan is acceptable (<10 docs).",
    ),
    "user_settings": _Overlay(
        feature="settings",
        entity="UserSettings",
        logical_unique=("user_id",),
        query_patterns=("point read by user_id", "admin list updated_at desc"),
        relationships=("1—N email_connections; 1—N settings_audit_log",),
        ru_note="Point read ~1 RU. Version field is optimistic concurrency, not an index.",
    ),
    "email_connections": _Overlay(
        feature="settings",
        entity="EmailConnection",
        logical_unique=("user_id", "provider", "status=active"),
        query_patterns=("user+provider", "subscription_expires_at renewals", "account_email lookup"),
        relationships=("N—1 user_settings; tokens excluded from index",),
        ru_note="Token paths are excluded so encrypted blobs do not inflate the index.",
    ),
    "settings_audit_log": _Overlay(
        feature="settings",
        entity="SettingsAudit",
        query_patterns=("user_id + created_at desc", "entity_id + created_at desc"),
        relationships=("immutable; retained after GDPR purge of live settings",),
        ru_note="Compliance log — no TTL. History pages stay in-partition.",
    ),
    "resumes": _Overlay(
        feature="resumes",
        entity="Resume",
        logical_unique=("user_id", "id"),
        query_patterns=("user_id + is_deleted + updated_at desc", "processing_status", "checksum_sha256"),
        relationships=("1—N children embedded; 1—N resume_parse_events",),
        ru_note="Library list of ~20 resumes is a single partitioned query (~5 RU).",
    ),
    "run_resume_selections": _Overlay(
        feature="resumes",
        entity="RunResumeSelection",
        logical_unique=("run_id",),
        query_patterns=("point read by run_id", "user_id + created_at desc"),
        relationships=("N—1 resumes; reject if is_deleted",),
        ru_note="Document id equals run_id so uniqueness is free.",
    ),
    "resume_parse_events": _Overlay(
        feature="resumes",
        entity="ResumeParseEvent",
        query_patterns=("resume_id + created_at desc",),
        relationships=("append-only parse/edit log",),
        ru_note="PK resume_id keeps the timeline in one partition.",
    ),
    "job_sources": _Overlay(
        feature="job_sources",
        entity="JobSource",
        logical_unique=("id",),
        query_patterns=("list greenhouse|lever",),
        ru_note="Two seeded rows; negligible RU.",
    ),
    "source_tenants": _Overlay(
        feature="job_sources",
        entity="SourceTenant",
        unique_keys=(("/tenant_key",),),
        logical_unique=("source_id", "tenant_key"),
        query_patterns=("source_id + tenant_key",),
        ru_note="Unique tenant_key per source partition prevents duplicate boards.",
    ),
    "source_fetch_runs": _Overlay(
        feature="job_sources",
        entity="SourceFetchRun",
        query_patterns=("source_tenant_id + started_at desc",),
        ru_note="Run history is per tenant partition.",
    ),
    "fetch_requests": _Overlay(
        feature="job_sources",
        entity="FetchRequest",
        default_ttl=30 * DAY,
        query_patterns=("run_id", "tenant + request_ts", "status_code"),
        ru_note="Transient HTTP attempts — 30-day TTL. Indexing status_code is cheap.",
    ),
    "fetch_cursors": _Overlay(
        feature="job_sources",
        entity="FetchCursor",
        unique_keys=(("/endpoint",),),
        logical_unique=("source_tenant_id", "endpoint"),
        query_patterns=("tenant + endpoint point read",),
        ru_note="One row per endpoint; always a point read.",
    ),
    "job_postings_raw": _Overlay(
        feature="job_sources",
        entity="JobPostingRaw",
        logical_unique=("source_tenant_id", "source_posting_id", "is_current=true"),
        default_ttl=90 * DAY,
        query_patterns=("tenant + source_posting_id", "dedupe_hash", "is_current", "seen_last_at"),
        relationships=("N—1 job_postings_canonical via job_posting_links; payload in Blob",),
        ru_note="TTL 90d for scrape snapshots. Unique source_posting_id is per tenant. Body is excluded via blob offload.",
    ),
    "job_postings_canonical": _Overlay(
        feature="job_sources",
        entity="JobPosting",
        logical_unique=("canonical_key", "dedupe_hash"),
        query_patterns=("canonical_key", "dedupe_hash", "is_active"),
        relationships=("1—N raw via links; 1—N Application/matches",),
        ru_note="PK /id so dedup lookups use indexed fields (~3 RU) not partition scans.",
    ),
    "job_posting_links": _Overlay(
        feature="job_sources",
        entity="JobPostingLink",
        logical_unique=("raw_id",),
        query_patterns=("raw_id point read", "canonical_id"),
        ru_note="PK raw_id enforces one canonical mapping per raw record.",
    ),
    "source_rate_limits": _Overlay(
        feature="job_sources",
        entity="SourceRateLimit",
        query_patterns=("source_tenant_id point read", "backoff_until"),
        ru_note="Hot write path; keep documents tiny (no payload).",
    ),
    "crawl_schedules": _Overlay(
        feature="job_sources",
        entity="CrawlSchedule",
        query_patterns=("next_run_after where is_paused = false",),
        ru_note="Scheduler polls; composite next_run_after + is_paused avoids a full scan.",
    ),
    "email_accounts": _Overlay(
        feature="mail",
        entity="EmailAccount",
        logical_unique=("id", "user_id+provider"),
        query_patterns=("point read by id", "list by user_id"),
        ru_note="Few accounts per user; point reads.",
    ),
    "email_threads": _Overlay(
        feature="mail",
        entity="MailThread",
        unique_keys=(("/graph_conversation_id",),),
        logical_unique=("email_account_id", "graph_conversation_id"),
        query_patterns=("account + last_message_at desc", "job_posting_id", "application_id"),
        ru_note="Inbox pages of 25 ~5 RU with last_message_at composite.",
    ),
    "email_messages": _Overlay(
        feature="mail",
        entity="EmailMessage",
        unique_keys=(("/graph_message_id",),),
        logical_unique=("email_account_id", "graph_message_id"),
        query_patterns=("thread + received_at desc", "delivery_status", "graph_message_id"),
        ru_note="Idempotent Graph ingest relies on unique graph_message_id per account.",
    ),
    "email_recipients": _Overlay(
        feature="mail",
        entity="EmailRecipient",
        query_patterns=("message_id list",),
        ru_note="Child rows; queried with parent message.",
    ),
    "email_attachments": _Overlay(
        feature="mail",
        entity="EmailAttachment",
        query_patterns=("message_id list",),
        relationships=("bytes in Blob; DB stores uri + metadata only",),
        ru_note="Metadata only — never index binary.",
    ),
    "email_drafts": _Overlay(
        feature="mail",
        entity="EmailDraft",
        query_patterns=("thread or account list",),
        ru_note="Low volume.",
    ),
    "graph_sync_cursors": _Overlay(
        feature="mail",
        entity="GraphSyncCursor",
        logical_unique=("email_account_id", "mode"),
        query_patterns=("account point read",),
        ru_note="One cursor document per mailbox.",
    ),
    "graph_subscriptions": _Overlay(
        feature="mail",
        entity="GraphSubscription",
        query_patterns=("account point read", "expires_at"),
        ru_note="Webhook renewal scan is tiny.",
    ),
    "email_ingestion_events": _Overlay(
        feature="mail",
        entity="EmailIngestionEvent",
        default_ttl=30 * DAY,
        query_patterns=("account + created_at desc",),
        ru_note="Transient ingest log — 30-day TTL.",
    ),
    "email_link_audits": _Overlay(
        feature="mail",
        entity="EmailLinkAudit",
        query_patterns=("thread + created_at",),
        ru_note="Low volume linking audit.",
    ),
    "email_templates": _Overlay(
        feature="mail",
        entity="EmailTemplate",
        query_patterns=("point read by id",),
        ru_note="System templates; PK /id.",
    ),
    "recommendations": _Overlay(
        feature="learning",
        entity="Recommendation",
        query_patterns=("user_id + generated_at desc", "weight_config_id", "status"),
        relationships=("0—1 decision_log per user",),
        ru_note="Decision affinity: same PK as decision_log.",
        indexing_policy=_policy(
            [
                {"path": "/user_id", "order": "ascending"},
                {"path": "/generated_at", "order": "descending"},
            ],
            [{"path": "/weight_config_id", "order": "ascending"}],
            [{"path": "/status", "order": "ascending"}],
        ),
    ),
    "decision_log": _Overlay(
        feature="learning",
        entity="DecisionLog",
        unique_keys=(("/recommendation_id",),),
        logical_unique=("recommendation_id", "user_id"),
        query_patterns=("user_id + decided_at desc", "recommendation_id"),
        indexing_policy=_policy(
            [
                {"path": "/user_id", "order": "ascending"},
                {"path": "/decided_at", "order": "descending"},
            ],
            [{"path": "/recommendation_id", "order": "ascending"}],
        ),
        ru_note="One decision per recommendation per user via unique key.",
    ),
    "model_params": _Overlay(
        feature="learning",
        entity="ModelParams",
        query_patterns=("user_id active params",),
        indexing_policy=_policy([{"path": "/user_id", "order": "ascending"}]),
        ru_note="One active param set per user.",
    ),
    "weight_config": _Overlay(
        feature="learning",
        entity="WeightConfig",
        logical_unique=("weight_config_id",),
        query_patterns=("point read; is_active lookup",),
        indexing_policy=_policy([{"path": "/is_active", "order": "ascending"}]),
        ru_note="Catalog sized; at most one is_active=true (app-enforced).",
    ),
    "weight_tuning_event": _Overlay(
        feature="learning",
        entity="WeightTuningEvent",
        query_patterns=("point read by tuning_event_id",),
        indexing_policy=_policy(
            [
                {"path": "/created_at", "order": "descending"},
            ]
        ),
        ru_note="Low write volume.",
    ),
    "metrics_snapshot": _Overlay(
        feature="learning",
        entity="MetricsSnapshot",
        query_patterns=("weight_config_id + window_end desc", "scope_type + scope_ref"),
        indexing_policy=_policy(
            [
                {"path": "/weight_config_id", "order": "ascending"},
                {"path": "/window_end", "order": "descending"},
            ],
            [
                {"path": "/scope_type", "order": "ascending"},
                {"path": "/scope_ref", "order": "ascending"},
            ],
        ),
        ru_note="Frozen historical metrics; PK scope_ref.",
    ),
    "auto_apply_attempts": _Overlay(
        feature="auto_apply",
        entity="Application",
        query_patterns=("user_id + status", "vendor + source_application_id"),
        relationships=("1—N packages, submits, status_events, webhooks",),
        ru_note="Queue of in-flight attempts is a partitioned status filter ~3 RU.",
    ),
    "apply_packages": _Overlay(
        feature="auto_apply",
        entity="ApplyPackage",
        query_patterns=("auto_apply_id point/list",),
        ru_note="PK auto_apply_id colocates the frozen package.",
    ),
    "resume_variants": _Overlay(
        feature="auto_apply",
        entity="ResumeVariant",
        query_patterns=("user_id list",),
        relationships=("bytes in Blob",),
        ru_note="Reuse across attempts; user partition.",
    ),
    "cover_letters": _Overlay(
        feature="auto_apply",
        entity="CoverLetter",
        query_patterns=("user_id list",),
        ru_note="Metadata + blob uri.",
    ),
    "form_autofill_values": _Overlay(
        feature="auto_apply",
        entity="FormAutofillValue",
        unique_keys=(("/vendor", "/field_key"),),
        logical_unique=("auto_apply_id", "vendor", "field_key"),
        query_patterns=("auto_apply_id + vendor + field_key",),
        ru_note="Required-field completeness is an in-partition query.",
    ),
    "vendor_field_mappings": _Overlay(
        feature="auto_apply",
        entity="VendorFieldMapping",
        query_patterns=("vendor partition list",),
        ru_note="Small mapping catalog per vendor.",
    ),
    "submit_requests": _Overlay(
        feature="auto_apply",
        entity="SubmitRequest",
        unique_keys=(("/idempotency_key",),),
        logical_unique=("vendor", "idempotency_key"),
        query_patterns=("auto_apply_id + status", "vendor + vendor_application_id"),
        ru_note="Unique idempotency_key per attempt partition stops duplicate submits.",
    ),
    "status_events": _Overlay(
        feature="auto_apply",
        entity="StatusEvent",
        query_patterns=("auto_apply_id + created_ts desc",),
        ru_note="Append-only; 18-month retention via purge job, not TTL.",
    ),
    "webhook_callbacks": _Overlay(
        feature="auto_apply",
        entity="WebhookCallback",
        unique_keys=(("/dedupe_key",),),
        logical_unique=("vendor", "vendor_application_id", "dedupe_key"),
        default_ttl=90 * DAY,
        query_patterns=("vendor_application_id partition", "dedupe_key"),
        ru_note="TTL 90 days per Auto-Apply PRD. Unique dedupe_key drops duplicate vendor posts.",
    ),
}


_FEATURE_LOADERS: tuple[tuple[str, Callable[[], list[dict[str, Any]]]], ...] = (
    ("review", lambda: _load("app.review.containers", "container_specs")),
    ("matching", lambda: _load("app.matching.containers", "container_specs")),
    ("settings", lambda: _load("app.settings.containers", "container_specs")),
    ("resumes", lambda: _load("app.resumes.containers", "container_specs")),
    ("job_sources", lambda: _load("app.job_sources.containers", "container_specs")),
    ("mail", lambda: _load("app.mail.containers", "container_specs")),
    ("learning", lambda: _load("app.learning.containers", "container_specs")),
    ("auto_apply", lambda: _load("app.auto_apply.containers", "container_specs")),
)


def _load(module: str, attr: str) -> list[dict[str, Any]]:
    from importlib import import_module

    return list(getattr(import_module(module), attr)())


def _platform_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "users",
            "partition_key": "/id",
            "indexing_policy": _policy(
                [{"path": "/status", "order": "ascending"}, {"path": "/created_at", "order": "descending"}]
            ),
        },
        {
            "id": "event_log",
            "partition_key": "/user_id",
            "indexing_policy": _OVERLAYS["event_log"].indexing_policy,
        },
        {
            "id": "schema_migrations",
            "partition_key": "/id",
            "indexing_policy": _policy([{"path": "/applied_at", "order": "descending"}]),
        },
    ]


def _merge(raw: dict[str, Any], feature_hint: str) -> ContainerSpec:
    overlay = _OVERLAYS.get(raw["id"])
    feature = overlay.feature if overlay else feature_hint
    entity = overlay.entity if overlay else raw["id"]
    indexing = (overlay.indexing_policy if overlay and overlay.indexing_policy else None) or raw.get(
        "indexing_policy"
    ) or DEFAULT_INDEXING
    return ContainerSpec(
        id=raw["id"],
        feature=feature,
        entity=entity,
        partition_key=raw["partition_key"],
        indexing_policy=indexing,
        unique_keys=overlay.unique_keys if overlay else (),
        logical_unique=overlay.logical_unique if overlay else (),
        default_ttl=overlay.default_ttl if overlay else None,
        query_patterns=overlay.query_patterns if overlay else (),
        relationships=overlay.relationships if overlay else (),
        ru_note=overlay.ru_note if overlay else "Default /* index; measure before adding composites.",
    )


def container_catalog() -> list[ContainerSpec]:
    """All Cosmos containers: platform + every Database PRD feature."""
    merged: dict[str, ContainerSpec] = {}
    for raw in _platform_specs():
        merged[raw["id"]] = _merge(raw, "platform")
    for feature, loader in _FEATURE_LOADERS:
        for raw in loader():
            merged[raw["id"]] = _merge(raw, feature)
    return [merged[key] for key in sorted(merged)]


def container_by_id(container_id: str) -> ContainerSpec:
    for spec in container_catalog():
        if spec.id == container_id:
            return spec
    raise KeyError(container_id)


def core_container_ids() -> tuple[str, ...]:
    from app.storage.entities import CORE_ENTITIES

    return tuple(item["container"] for item in CORE_ENTITIES.values())


def cosmos_create_kwargs(spec: ContainerSpec) -> dict[str, Any]:
    """Keyword args for ``DatabaseProxy.create_container_if_not_exists``."""
    from azure.cosmos import PartitionKey

    kwargs: dict[str, Any] = {
        "id": spec.id,
        "partition_key": PartitionKey(path=spec.partition_key),
        "indexing_policy": spec.indexing_policy,
    }
    policy = spec.unique_key_policy()
    if policy:
        kwargs["unique_key_policy"] = policy
    if spec.default_ttl is not None:
        kwargs["default_ttl"] = spec.default_ttl
    # Serverless accounts reject offer_throughput; omit RU so local + cloud stay idempotent.
    return kwargs


def ensure_all_containers(database: Any) -> list[str]:
    created: list[str] = []
    for spec in container_catalog():
        database.create_container_if_not_exists(**cosmos_create_kwargs(spec))
        created.append(spec.id)
    return created


def user_scoped_containers() -> list[ContainerSpec]:
    """Containers whose partition key is ``/user_id`` (GDPR delete affinity)."""
    return [spec for spec in container_catalog() if spec.partition_key == "/user_id"]


def ttl_containers() -> list[ContainerSpec]:
    return [spec for spec in container_catalog() if spec.default_ttl is not None]


def render_cosmos_schema() -> str:
    """Markdown schema for docs/cosmos.schema.md — keep committed copy in sync."""
    lines = [
        "# Cosmos DB schema",
        "",
        "Generated from `app.storage.catalog` and the Database PRDs.",
        "Unique-key paths omit the partition key (Cosmos unique keys are per partition).",
        "TTL is reserved for transient scrape/ingest/webhook rows; durable history is purged by job.",
        "",
        "| Container | Feature | Entity | Partition key | TTL (days) | Unique keys | Composites |",
        "|---|---|---|---|---|---|---|",
    ]
    for spec in container_catalog():
        ttl = "" if spec.default_ttl is None else str(spec.default_ttl // 86_400)
        unique = "; ".join("+".join(paths) for paths in spec.unique_keys) or "—"
        composites = len(spec.indexing_policy.get("compositeIndexes") or [])
        lines.append(
            f"| `{spec.id}` | {spec.feature} | {spec.entity} | `{spec.partition_key}` | {ttl or '—'} | {unique} | {composites} |"
        )
    lines.extend(["", "## Query patterns and RU notes", ""])
    for spec in container_catalog():
        lines.append(f"### `{spec.id}`")
        lines.append("")
        if spec.query_patterns:
            for pattern in spec.query_patterns:
                lines.append(f"- Query: {pattern}")
        if spec.relationships:
            for rel in spec.relationships:
                lines.append(f"- Rel: {rel}")
        if spec.logical_unique:
            lines.append(f"- Logical unique: `{', '.join(spec.logical_unique)}`")
        lines.append(f"- RU: {spec.ru_note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def indexing_report() -> list[dict[str, Any]]:
    rows = []
    for spec in container_catalog():
        composites = spec.indexing_policy.get("compositeIndexes") or []
        excluded = spec.indexing_policy.get("excludedPaths") or []
        rows.append(
            {
                "id": spec.id,
                "feature": spec.feature,
                "partition_key": spec.partition_key,
                "composite_count": len(composites),
                "excluded_paths": [item.get("path") for item in excluded],
                "ru_note": spec.ru_note,
            }
        )
    return rows
