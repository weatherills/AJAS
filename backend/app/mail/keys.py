"""Hashes, ids, and timestamps for Email Ingestion."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.mail.constants import TEMPLATE_VARS

TEMPLATE_RE = re.compile(r"\{(" + "|".join(TEMPLATE_VARS) + r")\}")


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str):
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def body_hash(body_text: str, body_html: str | None = None) -> str:
    return sha256_text(f"{body_text}\n{body_html or ''}")


def apply_template(text: str, variables: dict[str, str] | None) -> str:
    values = {key: (variables or {}).get(key, "") for key in TEMPLATE_VARS}

    def repl(match: re.Match[str]) -> str:
        return values.get(match.group(1), "") or match.group(0)

    return TEMPLATE_RE.sub(repl, text)


def unfilled_template_vars(text: str) -> list[str]:
    return sorted(set(TEMPLATE_RE.findall(text)))


def snippet_of(text: str, limit: int = 140) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def hours_ago(hours: float, *, now: str | None = None) -> str:
    stamp = parse_ts(now or utc_now()) - timedelta(hours=hours)
    return stamp.isoformat().replace("+00:00", "Z")
