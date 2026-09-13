"""Outbound HTTP host allowlist for adapters and Graph."""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import get_settings


def allowed_hosts() -> set[str]:
    raw = get_settings().outbound_allowlist or ""
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def parse_policy(raw: str) -> list[str]:
    return sorted({part.strip().lower() for part in (raw or "").split(",") if part.strip()})


def policy_text(hosts: list[str] | set[str]) -> str:
    return ", ".join(sorted({host.strip().lower() for host in hosts if host.strip()}))


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    allowed = allowed_hosts()
    if host in allowed:
        return True
    return any(host.endswith("." + item) for item in allowed)
