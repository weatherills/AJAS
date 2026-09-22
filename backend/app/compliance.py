"""SOC 2, DPA, subprocessors, and tamper-evident audit contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.matching.keys import utc_now
from app.privacy_review import has_raw_pii, scrub_v2
from app.storage.catalog import container_catalog
from app.storage.pii import MASK_PATHS, pii_paths

SOC2_CONTROLS: tuple[dict[str, Any], ...] = (
    {
        "id": "CC6.1",
        "category": "security",
        "name": "Logical access",
        "owner": "platform",
        "due": "2026-10-15",
        "evidence": ("JWT on HTTP", "dev Bearer isolated", "FLAG defaults off"),
        "status": "implemented",
    },
    {
        "id": "CC6.6",
        "category": "security",
        "name": "Encryption at rest / in transit",
        "owner": "platform",
        "due": "2026-10-15",
        "evidence": ("HTTPS", "Cosmos encryption", "settings token_blob sealed"),
        "status": "implemented",
    },
    {
        "id": "CC7.2",
        "category": "security",
        "name": "Monitoring and alerting",
        "owner": "ops",
        "due": "2026-10-15",
        "evidence": ("app.storage.ops alerts", "slo_snapshot", "ingestion_alerts"),
        "status": "implemented",
    },
    {
        "id": "A1.2",
        "category": "availability",
        "name": "Backups and restore",
        "owner": "platform",
        "due": "2026-10-30",
        "evidence": ("scripts/backup_storage.py", "app.storage.backup", "cosmos-archive"),
        "status": "implemented",
    },
    {
        "id": "C1.1",
        "category": "confidentiality",
        "name": "PII minimization and redaction",
        "owner": "privacy",
        "due": "2026-10-15",
        "evidence": ("app.storage.pii", "privacy_review.scrub_v2", "MASK_PATHS"),
        "status": "implemented",
    },
    {
        "id": "CC8.1",
        "category": "security",
        "name": "Change management",
        "owner": "platform",
        "due": "2026-11-01",
        "evidence": ("GitHub PRs", "schema_migrations", "CI pytest"),
        "status": "partial",
        "gap": "Formal CAB not required for v1; Git history is the change log.",
    },
)

GAPS: tuple[dict[str, Any], ...] = (
    {
        "control": "CC8.1",
        "risk": "medium",
        "remediation": "Keep PRs required for main; record schema_migrations on every catalog change.",
        "timeline": "ongoing",
    },
    {
        "control": "C1.2",
        "risk": "low",
        "remediation": "Legal review of DPA template before customer signature.",
        "timeline": "before first paid tenant",
    },
)

SUBPROCESSORS: tuple[dict[str, Any], ...] = (
    {"name": "Microsoft Azure", "role": "IaaS/PaaS", "data": "all tenant data", "region": "configured Azure region", "dpa": True},
    {"name": "Azure Cosmos DB", "role": "database", "data": "job/match/resume/mail metadata", "region": "same as account", "dpa": True},
    {"name": "Azure Blob Storage", "role": "object store", "data": "resumes, raw postings, mail attachments", "region": "same as account", "dpa": True},
    {"name": "Azure OpenAI", "role": "embeddings/chat", "data": "resume and JD text snippets", "region": "deployment region", "dpa": True},
    {"name": "Microsoft Graph", "role": "mail", "data": "mailbox messages the user connects", "region": "tenant M365", "dpa": True},
)

DPA_TEMPLATE = """# Data Processing Addendum (template v1)

This DPA is a baseline for legal review, not a signed contract.

1. Roles. AJAS is the processor; the customer is the controller of candidate and mailbox data.
2. Subject matter. Job applications, resumes, match scores, recruiter email, and audit logs.
3. Duration. Term of the service plus retention windows in the data map.
4. Nature. Hosting, matching, auto-apply, and email ingestion.
5. Types of data. Identity, contact, resume content, job applications, mail metadata, telemetry.
6. Data subjects. Job seekers who use AJAS and recruiters they correspond with.
7. Subprocessors. See the inventory (Azure, Cosmos, Blob, OpenAI, Graph).
8. International transfers. SCCs apply when data leaves the UK/EEA; Azure regions as configured.
9. Security. Encryption in transit, Cosmos encryption at rest, JWT/RBAC, PII redaction in logs.
10. Deletion. GDPR delete path purges user-scoped containers; audit receipts are retained.
"""


def data_map() -> list[dict[str, Any]]:
    rows = []
    for spec in container_catalog():
        rows.append(
            {
                "container": spec.id,
                "purpose": spec.entity,
                "storage": "cosmos",
                "partition": spec.partition_key,
                "retentionDays": None if spec.default_ttl is None else spec.default_ttl // 86_400,
                "pii": list(pii_paths(spec.id)),
                "access": "JWT user-scoped DAL",
                "lawfulBasis": "contract / legitimate interest (job search)",
            }
        )
    return rows


def soc2_inventory() -> dict[str, Any]:
    return {
        "controls": [dict(row) for row in SOC2_CONTROLS],
        "ownership": {row["id"]: {"owner": row["owner"], "due": row["due"]} for row in SOC2_CONTROLS},
        "gaps": [dict(row) for row in GAPS],
        "evidence": {row["id"]: list(row["evidence"]) for row in SOC2_CONTROLS},
    }


def evidence_map() -> dict[str, Any]:
    return {
        "logs": "app.audit + matching records telemetry + privacy_audit_log",
        "alerts": "app.storage.ops.evaluate_alerts",
        "backups": "app.storage.backup / scripts/backup_storage.py",
        "rbac": "JWT scopes + feature flags default off",
        "changeManagement": "git + schema_migrations",
        "cadence": "quarterly evidence pull",
    }


_CHAIN: list[dict[str, Any]] = []


def reset_audit_chain() -> None:
    _CHAIN.clear()


def _secret() -> bytes:
    return hashlib.sha256(b"ajas-audit-chain").digest()


def append_audit(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    previous = _CHAIN[-1]["hash"] if _CHAIN else "genesis"
    body = scrub_v2({"action": action, "at": utc_now(), "payload": payload, "prev": previous})
    blob = json.dumps(body, sort_keys=True, default=str)
    digest = hmac.new(_secret(), blob.encode("utf-8"), hashlib.sha256).hexdigest()
    row = {**body, "hash": digest, "prev": previous}
    _CHAIN.append(row)
    return row


def verify_audit_chain(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    chain = list(rows if rows is not None else _CHAIN)
    prev = "genesis"
    for index, row in enumerate(chain):
        expected_prev = prev
        body = {key: value for key, value in row.items() if key != "hash"}
        blob = json.dumps(body, sort_keys=True, default=str)
        digest = hmac.new(_secret(), blob.encode("utf-8"), hashlib.sha256).hexdigest()
        if row.get("prev") != expected_prev or row.get("hash") != digest:
            return {"ok": False, "brokenAt": index}
        if has_raw_pii(str(row.get("payload") or "")):
            return {"ok": False, "brokenAt": index, "reason": "pii"}
        prev = row["hash"]
    return {"ok": True, "length": len(chain)}


def subprocessors() -> dict[str, Any]:
    return {
        "items": [dict(row) for row in SUBPROCESSORS],
        "reviewCadence": "annual",
        "deprovision": "Revoke credentials, delete tenant data via GDPR path, confirm DPA offboarding.",
    }


def dpa_bundle() -> dict[str, Any]:
    return {
        "template": DPA_TEMPLATE,
        "dataMap": data_map(),
        "subprocessors": subprocessors()["items"],
        "maskPaths": {key: list(value) for key, value in MASK_PATHS.items()},
    }
