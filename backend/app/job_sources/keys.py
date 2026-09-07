"""Canonical key / hash helpers from the Job Source Database PRD."""

from __future__ import annotations

import hashlib
import re

_SLUG = re.compile(r"[^a-z0-9]+")


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str):
    from datetime import datetime, timezone

    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def slug(value: str | None) -> str:
    text = _SLUG.sub("-", normalize_text(value)).strip("-")
    return text or "unknown"


def canonical_key(*, title: str, location: str = "", namespace: str = "") -> str:
    """lower(trim(title)) + normalized(location) + dedupe_namespace → slug."""
    return f"{slug(title)}|{slug(location)}|{slug(namespace)}"


def sha256_hex(*parts: str) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dedupe_hash(*, key: str, body: str = "", employment_type: str = "") -> str:
    return sha256_hex(key, normalize_text(body), normalize_text(employment_type))


def response_hash(payload: str) -> str:
    return sha256_hex(payload)
