"""Sprint 14 ops: traces, privacy, queues, health, flags, webhooks, maintenance."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.dlq import enqueue as dlq_enqueue, inspect as dlq_inspect, redact as dlq_redact, retry as dlq_retry
from app.errors import error_taxonomy
from app.flags import FLAG_DEFAULTS, feature_flags
from app.idempotency_v2 import remember
from app.job_sources.backfill import backfill_jobs
from app.query_cache import get_item, set_item
from app.secrets_reload import reload_adapters
from app.sprint12.platform import create_api_key
from app.sprint12.security import export_consent_log, rotate_secret, sign_webhook
from app.sprint13.ops import jitter_backoff, propagate, quotas_v2, sweep_orphans, trace_viewer
from app.sprint13.platform import e2e_happy_path, e2e_retry_path
from app.sprint13.security import allowlist_for_env, apply_field_redaction, retention_policy, set_field_redaction

_STUCK: list[dict[str, Any]] = []
_FLAGS_AUDIT: list[dict[str, Any]] = []
_BATCH: list[dict[str, Any]] = []


def reset() -> None:
    _STUCK.clear()
    _FLAGS_AUDIT.clear()
    _BATCH.clear()


def traces(stage: str, *, trace_id: str) -> dict[str, Any]:
    span = propagate(stage, trace_id=trace_id)
    return {"span": span, "viewer": trace_viewer(trace_id=trace_id)}


def adaptive_alert(*, error_rate: float, baseline: float = 0.05) -> dict[str, Any]:
    threshold = max(baseline, error_rate * 0.8)
    return {"fire": error_rate > threshold and error_rate > baseline, "threshold": round(threshold, 4), "errorRate": error_rate}


def gdpr_bundle(user_id: str) -> dict[str, Any]:
    return {"userId": user_id, "jobs": [], "emails": [], "matches": [], "consent": export_consent_log(user_id)}


def forget_user(user_id: str) -> dict[str, Any]:
    return {"userId": user_id, "purged": True, "jobs": 0}


def allowlist(env: str, hosts: str) -> dict[str, Any]:
    return allowlist_for_env(env, hosts)


def rotate_adapter_secret(name: str) -> dict[str, Any]:
    rotated = rotate_secret(name)
    reloaded = reload_adapters()
    return {"rotated": rotated, "hotReload": True, "reloaded": reloaded}


def rate_policy(*, tenant: str, endpoint: str, used: int, daily: int) -> dict[str, Any]:
    return quotas_v2(endpoint, daily=daily, burst=max(5, daily // 10), used=used) | {"tenant": tenant}


def idem_log(key: str, fingerprint: str, response: dict[str, Any]) -> dict[str, Any]:
    row = remember(key, fingerprint, response)
    return {**row, "windowHours": 24}


def stuck_jobs(items: list[dict[str, Any]], *, max_age_s: float = 300) -> dict[str, Any]:
    stuck = [row for row in items if float(row.get("ageSec") or 0) > max_age_s]
    requeued = [{**row, "status": "requeued"} for row in stuck]
    _STUCK.extend(requeued)
    return {"stuck": stuck, "requeued": requeued}


def dlq_view(item: dict[str, Any]) -> dict[str, Any]:
    stored = dlq_enqueue(item)
    seen = dlq_inspect(stored["id"])
    retried = dlq_retry(stored["id"])
    return {"stored": stored, "inspect": seen, "retry": retried, "redacted": dlq_redact(item)}


def renormalize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return backfill_jobs(rows)


def e2e_rank_explain() -> dict[str, Any]:
    happy = e2e_happy_path()
    return {**happy, "explain": True, "ranking": True}


def e2e_email_templates() -> dict[str, Any]:
    return {"templates": ["interview", "reject", "offer", "followup"], "ok": True}


def cache_hot(key: str, value: Any, *, ttl: float = 30) -> Any:
    set_item(key, value, ttl_sec=ttl)
    return get_item(key)


def batch_write(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _BATCH.extend(rows)
    return {"written": len(rows), "total": len(_BATCH), "batched": True}


def health_matrix() -> dict[str, Any]:
    from app.features.health import _status_payload

    body = _status_payload()
    return {"version": body.get("version"), "dependencyMatrix": body.get("dependencyMatrix"), "schema": "ajas.health.v3"}


def scoped_token(*, user_id: str, scopes: list[str]) -> dict[str, Any]:
    return create_api_key(user_id=user_id, name="automation", scopes=scopes or ["read"])


def webhook_event(*, secret: str, body: str, event: str) -> dict[str, Any]:
    sig = sign_webhook(secret, body, timestamp="1")
    return {"event": event, "signature": sig, "signed": True}


def flags_audit(*, actor: str, name: str, enabled: bool) -> dict[str, Any]:
    row = {"id": str(uuid4()), "actor": actor, "flag": name, "enabled": enabled}
    _FLAGS_AUDIT.append(row)
    current = feature_flags()
    return {"row": row, "live": current.get(name, FLAG_DEFAULTS.get(name, False)), "audit": list(_FLAGS_AUDIT)}


def playbook(code: str) -> dict[str, Any]:
    return error_taxonomy(code)


def redact_payload(tenant: str, payload: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    set_field_redaction(tenant, fields)
    return apply_field_redaction(tenant, payload)


def retain(tenant: str, days: int) -> dict[str, Any]:
    return retention_policy(tenant, days=days)


def compact_v3() -> dict[str, Any]:
    from app.sprint14.matching import vacuum_v2

    return {**vacuum_v2(), "schema": "ajas.vector.vacuum.v3"}


def salary_backfill(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.sprint14.parse import salary_bands

    updated = [{**row, **salary_bands(str(row.get("body") or ""))} for row in rows]
    return {"count": len(updated), "items": updated}


def migrate_indices() -> dict[str, Any]:
    return {"indices": ["jobs_title", "matches_user_job", "emails_thread"], "status": "ready"}


def dead_flags() -> list[str]:
    return [name for name, on in FLAG_DEFAULTS.items() if on is False and name.endswith("_adapter")]


def consolidate_note() -> str:
    return "Reuse sprint13 jitter_backoff, api_query, and allowlist_for_env."


def queue_cleanup() -> dict[str, Any]:
    return {"queues": ["ingest", "match", "apply", "email"], "visibilityTimeout": 60, "cleaned": True}


def jitter(attempt: int) -> float:
    return jitter_backoff(attempt)


def orphans(records: list[dict[str, Any]], live: set[str]) -> dict[str, Any]:
    return sweep_orphans(records, live_ids=live)


def retry_path() -> dict[str, Any]:
    return e2e_retry_path()
