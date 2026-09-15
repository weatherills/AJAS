"""Canonical key / hash helpers from the Job Source Database PRD."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

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


def normalize_apply_url(url: str | None) -> str:
    """Host + path only (no scheme, query, or fragment) for cross-source dedupe."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}"


def normalize_company(company: str | None) -> str:
    return normalize_text(company)


def dedupe_namespace(*, company: str = "", apply_url: str = "") -> str:
    """Cross-source merge key. Omits greenhouse/lever so the same role collapses."""
    return f"{normalize_company(company)}:{normalize_apply_url(apply_url)}"


def canonical_id_for(key: str) -> str:
    """Stable Cosmos id: sha1(canonical key)."""
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def sha256_hex(*parts: str) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def content_hash(
    *,
    title: str = "",
    company: str = "",
    location: str = "",
    employment_type: str = "",
    apply_url: str = "",
    description_text: str = "",
) -> str:
    """SHA256 over normalized title+company+location+type+apply_url+description."""
    return sha256_hex(
        normalize_text(title),
        normalize_company(company),
        normalize_text(location),
        normalize_text(employment_type),
        normalize_apply_url(apply_url),
        normalize_text(description_text),
    )


def dedupe_hash(*, key: str, body: str = "", employment_type: str = "") -> str:
    return sha256_hex(key, normalize_text(body), normalize_text(employment_type))


def response_hash(payload: str) -> str:
    return sha256_hex(payload)
