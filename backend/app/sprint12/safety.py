"""Red-team prompts, sensitive JD detection, scam jobs, tenant blocklists."""

from __future__ import annotations

import re
from typing import Any

_BLOCK: dict[str, dict[str, list[str]]] = {}

PROMPT_ABUSE = (
    "ignore previous instructions",
    "exfiltrate",
    "system prompt",
    "drop table",
    "wget http",
)

SENSITIVE = (
    "clearance required",
    "polygraph",
    "itar",
    "ssn",
    "unpaid trial",
    "crypto seed",
)

SCAM_MARKERS = (
    "wire transfer",
    "gift card",
    "whatsapp interview",
    "pay for equipment",
    "guaranteed income",
)


def reset() -> None:
    _BLOCK.clear()


def red_team(prompt: str) -> dict[str, Any]:
    text = (prompt or "").lower()
    hits = [marker for marker in PROMPT_ABUSE if marker in text]
    return {"blocked": bool(hits), "hits": hits, "action": "reject" if hits else "allow"}


def sensitive_jd(text: str) -> dict[str, Any]:
    blob = (text or "").lower()
    hits = [marker for marker in SENSITIVE if marker in blob]
    return {"warning": bool(hits), "hits": hits, "severity": "high" if hits else "none"}


def scam_job(job: dict[str, Any]) -> dict[str, Any]:
    blob = " ".join(str(job.get(key) or "") for key in ("title", "company", "description", "url")).lower()
    hits = [marker for marker in SCAM_MARKERS if marker in blob]
    lookalike = bool(re.search(r"g[o0]{2}gle|micr[o0]soft-careers", blob))
    if lookalike:
        hits.append("lookalike_domain")
    return {"spam": bool(hits), "hits": hits}


def set_blocklist(tenant_id: str, *, companies: list[str] | None = None, keywords: list[str] | None = None) -> dict[str, Any]:
    row = {
        "companies": [c.strip().lower() for c in companies or [] if c.strip()],
        "keywords": [k.strip().lower() for k in keywords or [] if k.strip()],
    }
    _BLOCK[tenant_id] = row
    return row


def blocked(tenant_id: str, job: dict[str, Any]) -> bool:
    rules = _BLOCK.get(tenant_id) or {"companies": [], "keywords": []}
    company = str(job.get("company") or "").lower()
    blob = f"{job.get('title') or ''} {job.get('description') or ''}".lower()
    if company in rules["companies"]:
        return True
    return any(keyword in blob for keyword in rules["keywords"])
