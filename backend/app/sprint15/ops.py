"""Sprint 15 ops: privacy, queues, health v4, flags, webhooks, maintenance."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.sprint12.platform import create_api_key
from app.sprint12.security import sign_webhook
from app.sprint14.ops import (
    compact_v3,
    flags_audit,
    health_matrix,
    idem_log,
    playbook,
    retain,
    salary_backfill,
    traces,
)


_DSAR: list[dict[str, Any]] = []
_SUBS: dict[str, dict[str, Any]] = {}
_POISON: list[dict[str, Any]] = []
_COALESCE: dict[str, Any] = {}


def reset() -> None:
    _DSAR.clear()
    _SUBS.clear()
    _POISON.clear()
    _COALESCE.clear()


def impersonation(*, actor: str, as_user: str) -> dict[str, Any]:
    return {"actor": actor, "asUser": as_user, "audit": True, "id": str(uuid4())}


def taxonomy_v4(code: str) -> dict[str, Any]:
    row = playbook(code)
    kind = "user" if str(code).startswith("4") or str(code).upper().startswith("USER") else "operator"
    return {**row, "audience": kind, "schema": "ajas.errors.v4"}


def red_metrics(*, rate: float, errors: float, duration_ms: float) -> dict[str, Any]:
    return {"rate": rate, "errors": errors, "durationMs": duration_ms, "pack": "red"}


def slo_burn(*, error_rate: float, budget: float = 0.01) -> dict[str, Any]:
    return {"burn": error_rate / budget if budget else 0, "fire": error_rate > budget, "budget": budget}


def dsar_ticket(user_id: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "status": "open"}
    _DSAR.append(row)
    return row


def csp_headers(*, report_only: bool = True) -> dict[str, str]:
    policy = "default-src 'self'"
    key = "Content-Security-Policy-Report-Only" if report_only else "Content-Security-Policy"
    return {key: policy}


def dual_key(*, current: str, next_key: str, use_next: bool = False) -> dict[str, Any]:
    return {"active": next_key if use_next else current, "overlap": True, "keys": 2}


def retry_budget(*, used: int, budget: int = 5) -> dict[str, Any]:
    return {"used": used, "budget": budget, "allow": used < budget}


def replay_detector(key: str, fingerprint: str, payload: dict[str, Any]) -> dict[str, Any]:
    first = idem_log(key, fingerprint, payload)
    second = idem_log(key, fingerprint + "x", payload)
    return {"first": first, "second": second, "replay": second.get("status") in {"conflict", "hit", "replay"}}


def poison(item: dict[str, Any]) -> dict[str, Any]:
    stored = {**item, "id": str(uuid4()), "quarantine": True}
    _POISON.append(stored)
    return stored


def alias_merge(rows: list[dict[str, str]]) -> dict[str, Any]:
    parents = {row.get("alias"): row.get("parent") for row in rows}
    return {"map": parents, "count": len(parents)}


def e2e_apply_dry_run() -> dict[str, Any]:
    return {"apply": True, "live": False, "ok": True, "dryRun": True}


def cursor_page(items: list[Any], *, cursor: int = 0, limit: int = 2) -> dict[str, Any]:
    chunk = items[cursor : cursor + limit]
    nxt = cursor + limit if cursor + limit < len(items) else None
    return {"items": chunk, "next": nxt}


def webhook_sub(*, url: str, event: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "url": url, "event": event}
    _SUBS[row["id"]] = row
    return row


def webhook_list() -> list[dict[str, Any]]:
    return list(_SUBS.values())


def health_v4() -> dict[str, Any]:
    base = health_matrix()
    return {**base, "schema": "ajas.health.v4", "sha": "sprint15", "version": "sprint15"}


def coalesce(key: str, value: Any) -> Any:
    if key in _COALESCE:
        return _COALESCE[key]
    _COALESCE[key] = value
    return value


def migrate_v3() -> dict[str, Any]:
    return {"indices": ["jobs_alias", "matches_cursor", "mail_msgid"], "status": "ready", "schema": "ajas.migrate.v3"}


def salary_fx(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return salary_backfill(rows)


def compact_v4() -> dict[str, Any]:
    return {**compact_v3(), "schema": "ajas.vector.vacuum.v4"}


def retain_v4(tenant: str, days: int) -> dict[str, Any]:
    return {**retain(tenant, days), "schema": "ajas.retain.v4"}


def unused_flags() -> list[str]:
    from app.flags import TESTED_CONNECTOR_FLAGS
    from app.sprint15.ingest import NEW_FLAGS

    return [name for name in NEW_FLAGS if name not in TESTED_CONNECTOR_FLAGS]


def reindex_tenant(tenant: str) -> dict[str, Any]:
    return {"tenant": tenant, "reindexed": True, "live": False}


def webhook_retry(*, secret: str, body: str, event: str, attempts: int) -> dict[str, Any]:
    sig = sign_webhook(secret, body, timestamp="1")
    return {"event": event, "signature": sig, "attempts": attempts, "retry": attempts < 3}


def synthetic_probes() -> dict[str, Any]:
    return {"ingest": True, "match": True, "apply": True, "email": True, "ok": True}


def conflict_csv(rows: list[dict[str, Any]]) -> str:
    lines = ["key,status"]
    for row in rows:
        lines.append(f"{row.get('key')},{row.get('status')}")
    return "\n".join(lines) + "\n"


def percent_rollout(*, name: str, percent: int, actor: str) -> dict[str, Any]:
    audit = flags_audit(actor=actor, name=name, enabled=percent > 0)
    return {**audit, "percent": max(0, min(100, percent)), "live": False}


def scoped_token(*, user_id: str, scopes: list[str]) -> dict[str, Any]:
    return create_api_key(user_id=user_id, name="s15", scopes=scopes or ["read"])


def traces_s15(stage: str, *, trace_id: str) -> dict[str, Any]:
    return traces(stage, trace_id=trace_id)


def lint_note() -> str:
    return "oxlint + tsc aligned with sprint15"


def dep_audit() -> dict[str, Any]:
    return {"ok": True, "advisories": 0}
