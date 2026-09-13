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


_AUDIT: list[dict] = []


def reset_audit() -> None:
    _AUDIT.clear()


def set_policy(raw: str, *, actor: str = "admin") -> dict:
    hosts = parse_policy(raw)
    from app.matching.keys import utc_now

    event = {"actor": actor, "hosts": hosts, "at": utc_now(), "action": "allowlist.update"}
    _AUDIT.append(event)
    return {"hosts": hosts, "audit": event}


def audit_log() -> list[dict]:
    return list(_AUDIT)
