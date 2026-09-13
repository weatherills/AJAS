"""Outbound HTTP host allowlist for adapters and Graph."""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import get_settings


def allowed_hosts() -> set[str]:
    raw = get_settings().outbound_allowlist or ""
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    allowed = allowed_hosts()
    if host in allowed:
        return True
    return any(host.endswith("." + item) for item in allowed)
