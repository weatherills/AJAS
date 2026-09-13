"""API keys, SDK contract, pagination, analytics, legal, release, storage, CLI."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from app.mail.scan import scan_attachment
from app.matching.keys import utc_now
from app.pagination import MAX_LIMIT, MIN_LIMIT, normalize_limit, page_body
from app.ratelimit_v2 import hit as rate_hit
from app.sprint12.security import export_consent_log

_KEYS: dict[str, dict[str, Any]] = {}
_EVENTS: list[dict[str, Any]] = []
_LEGAL = {
    "terms": {"version": "2026-09-13", "url": "/legal#terms"},
    "privacy": {"version": "2026-09-13", "url": "/legal#privacy"},
}
_PENTEST: list[dict[str, Any]] = []
_STORAGE: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _KEYS.clear()
    _EVENTS.clear()
    _PENTEST.clear()
    _STORAGE.clear()


SCOPES = ("ingest", "match", "apply", "email", "read")


def create_api_key(*, user_id: str, name: str, scopes: list[str]) -> dict[str, Any]:
    unknown = [s for s in scopes if s not in SCOPES]
    if unknown:
        raise ValueError(f"unknown scopes: {unknown}")
    secret = uuid4().hex + uuid4().hex
    prefix = "ajas_live_"
    row = {
        "id": str(uuid4()),
        "userId": user_id,
        "name": name,
        "prefix": prefix,
        "suffix": secret[-4:],
        "scopes": list(scopes),
        "checksum": hashlib.sha256(secret.encode()).hexdigest()[:12],
        "revoked": False,
        "createdAt": utc_now(),
        "secret": prefix + secret,
    }
    _KEYS[row["id"]] = row
    return row


def revoke_api_key(key_id: str, *, user_id: str) -> bool:
    row = _KEYS.get(key_id)
    if not row or row["userId"] != user_id:
        return False
    row["revoked"] = True
    row.pop("secret", None)
    return True


def sdk_contract() -> dict[str, Any]:
    return {
        "package": "@ajas/client",
        "baseUrl": "/api",
        "auth": "Bearer",
        "resources": ["jobs", "matches", "reviews", "email", "settings"],
        "pagination": {"limit": "limit", "cursor": "cursor"},
    }


def rate_headers(tenant: str, endpoint: str, *, limit: int = 60) -> dict[str, str]:
    snap = rate_hit(tenant, endpoint, limit=limit)
    remaining = int(snap["remaining"])
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": "60",
    }


def cursor_page(items: list[Any], *, cursor: str | None, limit: int) -> dict[str, Any]:
    size = normalize_limit(limit)
    start = int(cursor or 0)
    window = items[start : start + size]
    nxt = str(start + size) if start + size < len(items) else None
    return page_body(window, next_cursor=nxt, extra={"limit": size})


def empty_state(kind: str) -> dict[str, str]:
    copy = {
        "jobs": "No jobs yet. Add a Greenhouse or Lever board in Settings.",
        "matches": "No matches above your threshold.",
        "email": "No recruiter threads yet.",
        "error": "Something went wrong. Retry from the banner or home.",
    }
    return {"kind": kind, "title": copy.get(kind, "Nothing here yet."), "cta": "#/"}


def knowledge_base() -> list[dict[str, str]]:
    return [
        {"id": "connect-email", "title": "Connect Microsoft 365", "body": "Settings → Email → Connect."},
        {"id": "threshold", "title": "Match threshold", "body": "Jobs at or above the slider land in Review."},
        {"id": "share", "title": "Share a match", "body": "Pro and Team plans can mint expiring links."},
    ]


def search_docs(q: str) -> list[dict[str, str]]:
    needle = q.lower()
    return [row for row in knowledge_base() if needle in row["title"].lower() or needle in row["body"].lower()]


CHANGELOG = [
    {"version": "12.0.0", "highlights": ["Tenancy", "Billing", "Dark mode", "fr/es locales"]},
    {"version": "11.0.0", "highlights": ["Career-page fixtures", "ANN recall", "Ops mute"]},
]


def warehouse_export(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"format": "ndjson", "count": len(rows), "target": "analytics.ajas.events"}


def funnel(events: list[str]) -> dict[str, int]:
    order = ["visit", "upload", "match", "review", "apply"]
    counts = {step: events.count(step) for step in order}
    return counts


def track_event(name: str, *, user_id: str, allow: bool) -> dict[str, Any] | None:
    if not allow:
        return None
    row = {"name": name, "userId": user_id, "at": utc_now()}
    _EVENTS.append(row)
    return row


def legal_bundle() -> dict[str, Any]:
    return dict(_LEGAL)


def file_pentest(*, title: str, severity: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "title": title, "severity": severity, "status": "triage"}
    _PENTEST.append(row)
    return row


def env_config(env: str) -> dict[str, Any]:
    return {
        "env": env,
        "AUTH_MODE": "aad" if env == "prod" else "dev",
        "FLAG_BULK_AUTO_APPLY": False,
        "secrets": ["COSMOS_CONNECTION_STRING", "AZURE_OPENAI_API_KEY", "MICROSOFT_CLIENT_SECRET"],
    }


def rollback_steps() -> list[str]:
    return [
        "Redeploy previous Container Apps revision",
        "Unset new FLAG_* settings",
        "Confirm GET /api/health version",
        "Watch golden signals for 15 minutes",
    ]


def release_checklist() -> list[str]:
    return [
        "pytest + vitest + tsc + oxlint green",
        "Flags default off for optional adapters",
        "Health version matches changelog",
        "Backup drill logged this month",
        "Rollback owner named",
    ]


def web_vitals_budget() -> dict[str, float]:
    return {"lcpMs": 2500, "inpMs": 200, "cls": 0.1}


def within_budget(sample: dict[str, float]) -> bool:
    budget = web_vitals_budget()
    return sample.get("lcpMs", 0) <= budget["lcpMs"] and sample.get("inpMs", 0) <= budget["inpMs"] and sample.get("cls", 0) <= budget["cls"]


def quota_put(blob: str, bytes_: int, *, cap: int = 10 * 1024 * 1024) -> dict[str, Any]:
    used = _STORAGE.get(blob, {}).get("bytes", 0) + bytes_
    if used > cap:
        return {"allowed": False, "used": used, "cap": cap}
    _STORAGE[blob] = {"bytes": used, "lifecycleDays": 90}
    return {"allowed": True, "used": used, "cap": cap}


def mime_allowed(name: str, content_type: str) -> bool:
    allowed = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".txt": "text/plain",
    }
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    expected = allowed.get(ext)
    return bool(expected and expected == content_type)


def scan_upload(content: bytes, *, file_name: str, content_type: str) -> dict[str, Any]:
    if not mime_allowed(file_name, content_type):
        return {"clean": False, "reason": "mime_mismatch"}
    result = scan_attachment(content, file_name=file_name)
    return {"clean": result.clean, "reason": result.reason, "engine": result.engine}


def cli_commands() -> list[str]:
    return ["ingest", "reindex", "backfill", "seed", "adapters"]


def iac_baseline() -> dict[str, Any]:
    return {
        "format": "bicep",
        "resources": ["functionApp", "cosmos", "storage", "keyVault", "containerApp"],
        "path": "infra/main.bicep",
    }


def consent_export(user_id: str) -> list[dict[str, Any]]:
    return export_consent_log(user_id)


def gdpr_csv(bundle: dict[str, Any]) -> str:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["collection", "id"])
    for collection in ("jobs", "emails", "matches", "resumes", "logs"):
        for item in bundle.get(collection) or []:
            writer.writerow([collection, item.get("id") if isinstance(item, dict) else item])
    return buf.getvalue()


def gdpr_bundle(*, user_id: str, tenant_id: str, records: dict[str, list]) -> dict[str, Any]:
    from app.privacy import export_bundle

    bundle = export_bundle(user_id=user_id, **{k: records.get(k) for k in ("jobs", "emails", "matches", "resumes", "logs")})
    bundle["tenantId"] = tenant_id
    bundle["csv"] = gdpr_csv(bundle)
    bundle["format"] = "ajas.gdpr.v2"
    return bundle


def list_api_keys(user_id: str) -> list[dict[str, Any]]:
    rows = []
    for row in _KEYS.values():
        if row["userId"] != user_id:
            continue
        rows.append({k: v for k, v in row.items() if k != "secret"})
    return rows


LIMITS = {"min": MIN_LIMIT, "max": MAX_LIMIT}
