"""PII CI hook, SAST stub, vulns, privacy UI, retention, allowlist, idempotency v3, playbooks."""

from __future__ import annotations

import re
from typing import Any

from app.allowlist import parse_policy
from app.errors import error_taxonomy
from app.idempotency_v2 import remember
from app.sprint12.security import redact_pii

_PII = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_VULNS: list[dict[str, Any]] = []
_REDACT: dict[str, list[str]] = {}
_RETENTION: dict[str, int] = {}


def reset() -> None:
    _VULNS.clear()
    _REDACT.clear()
    _RETENTION.clear()


def pii_scan_text(blob: str) -> dict[str, Any]:
    hits = _PII.findall(blob or "")
    return {"leaks": hits, "clean": not hits, "engine": "ajas.pii.ci.v1"}


def sast_findings(paths: list[str] | None = None) -> dict[str, Any]:
    scanned = paths or ["backend/app", "frontend/src"]
    return {"scanned": scanned, "critical": 0, "high": 0, "tool": "ajas.sast.stub"}


def file_vuln(*, title: str, severity: str, cve: str | None = None) -> dict[str, Any]:
    row = {"title": title, "severity": severity, "cve": cve, "status": "open" if severity in {"critical", "high"} else "triage"}
    _VULNS.append(row)
    return row


def remediate_critical() -> list[dict[str, Any]]:
    out = []
    for row in _VULNS:
        if row["severity"] == "critical":
            row["status"] = "fixed"
            out.append(row)
    return out


def set_field_redaction(tenant_id: str, fields: list[str]) -> dict[str, Any]:
    _REDACT[tenant_id] = [f.strip() for f in fields if f.strip()]
    return {"tenantId": tenant_id, "fields": _REDACT[tenant_id]}


def apply_field_redaction(tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields = set(_REDACT.get(tenant_id) or [])
    out = {}
    for key, value in payload.items():
        if key in fields:
            out[key] = "[redacted]"
        elif isinstance(value, str):
            out[key] = redact_pii(value, context="log")
        else:
            out[key] = value
    return out


def retention_policy(tenant_id: str, *, days: int) -> dict[str, Any]:
    if days < 7:
        raise ValueError("retention must be at least 7 days")
    _RETENTION[tenant_id] = int(days)
    return {"tenantId": tenant_id, "days": int(days)}


def allowlist_for_env(env: str, hosts: str) -> dict[str, Any]:
    parsed = parse_policy(hosts)
    gated = env == "prod"
    return {"env": env, "hosts": parsed, "gated": gated}


def resolve_conflict(key: str, fingerprint: str, response: dict[str, Any], *, strategy: str = "stored-wins") -> dict[str, Any]:
    result = remember(key, fingerprint, response)
    if result["status"] != "conflict":
        return result
    if strategy == "incoming-wins":
        remember(key + ":override", fingerprint, response)
        return {"status": "replaced", "strategy": strategy, "cached": response}
    return {**result, "strategy": strategy}


def playbook_for(code: str) -> dict[str, Any]:
    return error_taxonomy(code)
