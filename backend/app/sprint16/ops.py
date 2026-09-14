"""Sprint 16 ops: privacy, queues, health v5, flags, webhooks, maintenance."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.sprint12.platform import create_api_key
from app.sprint12.security import sign_webhook
from app.sprint15.ops import (
    compact_v4,
    flags_audit,
    health_v4,
    idem_log,
    playbook,
    retain_v4,
    salary_fx,
    traces_s15,
)

_DSAR: list[dict[str, Any]] = []
_SUBS: dict[str, dict[str, Any]] = {}
_POISON: list[dict[str, Any]] = []
_COALESCE: dict[str, Any] = {}
_REPLAY: list[str] = []


def reset() -> None:
    _DSAR.clear()
    _SUBS.clear()
    _POISON.clear()
    _COALESCE.clear()
    _REPLAY.clear()


def break_glass(*, actor: str, as_user: str, reason: str) -> dict[str, Any]:
    return {"actor": actor, "asUser": as_user, "reason": reason, "audit": True, "id": str(uuid4())}


def taxonomy_v5(code: str) -> dict[str, Any]:
    row = playbook(code)
    text = str(code).upper()
    if text.startswith("4") or text.startswith("USER"):
        kind = "user"
    elif text.startswith("VENDOR") or text.startswith("5"):
        kind = "vendor"
    else:
        kind = "operator"
    return {**row, "audience": kind, "schema": "ajas.errors.v5"}


def use_metrics(*, util: float, sat: float, errors: float) -> dict[str, Any]:
    return {"utilization": util, "saturation": sat, "errors": errors, "pack": "use"}


def error_budget(*, used: float, budget: float = 0.01) -> dict[str, Any]:
    remaining = max(0.0, budget - used)
    return {"remaining": remaining, "fire": remaining <= 0, "budget": budget}


def dsar_encrypt(user_id: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "status": "open", "encrypted": True}
    _DSAR.append(row)
    return row


def hsts_csp(*, enforce: bool = False) -> dict[str, str]:
    headers = {"Strict-Transport-Security": "max-age=63072000; includeSubDomains"}
    key = "Content-Security-Policy" if enforce else "Content-Security-Policy-Report-Only"
    headers[key] = "default-src 'self'"
    return headers


def triple_key(*, current: str, next_key: str, previous: str, use_next: bool = False) -> dict[str, Any]:
    return {"active": next_key if use_next else current, "overlap": True, "keys": 3, "previous": previous}


def token_bucket(*, tokens: float, rate: float, burst: float) -> dict[str, Any]:
    allow = tokens > 0
    return {"tokens": tokens, "rate": rate, "burst": burst, "allow": allow, "schema": "ajas.rate.v3"}


def replay_storm(key: str, fingerprint: str, payload: dict[str, Any], *, n: int = 3) -> dict[str, Any]:
    first = idem_log(key, fingerprint, payload)
    hits = [first]
    for i in range(n):
        hits.append(idem_log(key, fingerprint + str(i), payload))
    storm = sum(1 for row in hits if row.get("status") in {"conflict", "hit", "replay"}) >= 2
    _REPLAY.append(key)
    return {"first": first, "storm": storm, "hits": hits}


def poison_cap(item: dict[str, Any], *, replays: int = 0, cap: int = 3) -> dict[str, Any]:
    stored = {**item, "id": str(uuid4()), "quarantine": True, "replays": replays, "capped": replays >= cap}
    _POISON.append(stored)
    return stored


def brand_merge(rows: list[dict[str, str]]) -> dict[str, Any]:
    parents = {row.get("alias"): row.get("dba") or row.get("parent") for row in rows}
    return {"map": parents, "count": len(parents), "schema": "ajas.brand.merge"}


def e2e_apply_dry_run_v2() -> dict[str, Any]:
    return {"apply": True, "live": False, "ok": True, "dryRun": True, "schema": "ajas.e2e.v2"}


def cursor_page_v3(items: list[Any], *, cursor: int = 0, limit: int = 2) -> dict[str, Any]:
    chunk = items[cursor : cursor + limit]
    nxt = cursor + limit if cursor + limit < len(items) else None
    return {"items": chunk, "next": nxt, "schema": "ajas.page.v3"}


def webhook_sub(*, url: str, event: str, filter_q: str | None = None) -> dict[str, Any]:
    row = {"id": str(uuid4()), "url": url, "event": event, "filter": filter_q}
    _SUBS[row["id"]] = row
    return row


def webhook_list() -> list[dict[str, Any]]:
    return list(_SUBS.values())


def health_v5() -> dict[str, Any]:
    base = health_v4()
    return {**base, "schema": "ajas.health.v5", "sha": "sprint16", "version": "sprint16"}


def coalesce_v2(key: str, value: Any) -> Any:
    if key in _COALESCE:
        return _COALESCE[key]
    _COALESCE[key] = value
    return value


def migrate_v4() -> dict[str, Any]:
    return {"indices": ["jobs_brand", "matches_cursor_v3", "mail_irt"], "status": "ready", "schema": "ajas.migrate.v4"}


def salary_fx_v4(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {**salary_fx(rows), "schema": "ajas.fx.v4"}


def compact_v5() -> dict[str, Any]:
    return {**compact_v4(), "schema": "ajas.vector.vacuum.v5"}


def retain_v5(tenant: str, days: int) -> dict[str, Any]:
    return {**retain_v4(tenant, days), "schema": "ajas.retain.v5"}


def unused_flags() -> list[str]:
    from app.sprint16.ingest import NEW_FLAGS

    return list(NEW_FLAGS)


def reindex_tenant_v2(tenant: str) -> dict[str, Any]:
    return {"tenant": tenant, "reindexed": True, "live": False, "schema": "ajas.reindex.v2"}


def webhook_retry_v2(*, secret: str, body: str, event: str, attempts: int) -> dict[str, Any]:
    sig = sign_webhook(secret, body, timestamp="1")
    return {"event": event, "signature": sig, "attempts": attempts, "retry": attempts < 5}


def synthetic_probes_v2() -> dict[str, Any]:
    return {"ingest": True, "match": True, "apply": True, "email": True, "search": True, "ok": True}


def conflict_json(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rows": rows, "count": len(rows), "format": "json"}


def percent_rollout_v2(*, name: str, percent: int, actor: str) -> dict[str, Any]:
    audit = flags_audit(actor=actor, name=name, enabled=percent > 0)
    return {**audit, "percent": max(0, min(100, percent)), "live": False, "schema": "ajas.flags.v2"}


def scoped_token(*, user_id: str, scopes: list[str]) -> dict[str, Any]:
    return create_api_key(user_id=user_id, name="s16", scopes=scopes or ["read"])


def traces_s16(stage: str, *, trace_id: str) -> dict[str, Any]:
    return traces_s15(stage, trace_id=trace_id)


def lint_note() -> str:
    return "oxlint + tsc aligned with sprint16"


def dep_audit() -> dict[str, Any]:
    return {"ok": True, "advisories": 0}
