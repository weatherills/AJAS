"""Per-tenant, per-host cookie jars and session pools for optional adapters.

Live HTML scraping is out of the Job Source PRD. Jars are in-memory only so
tenants never share cookies. Empty jars are the fail-closed default.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

_JARS: dict[tuple[str, str], dict[str, str]] = {}
_SESSIONS: dict[tuple[str, str], list[str]] = defaultdict(list)


def reset() -> None:
    _JARS.clear()
    _SESSIONS.clear()


def put(*, tenant: str, host: str, name: str, value: str) -> dict[str, str]:
    key = (tenant, host.lower())
    jar = _JARS.setdefault(key, {})
    jar[name] = value
    return dict(jar)


def get(*, tenant: str, host: str) -> dict[str, str]:
    return dict(_JARS.get((tenant, host.lower())) or {})


def isolated(tenant_a: str, tenant_b: str, host: str) -> bool:
    return get(tenant=tenant_a, host=host) != get(tenant=tenant_b, host=host) or not get(tenant=tenant_a, host=host)


def borrow_session(*, tenant: str, host: str) -> dict[str, Any]:
    sid = uuid4().hex[:12]
    _SESSIONS[(tenant, host.lower())].append(sid)
    return {"tenant": tenant, "host": host, "sessionId": sid, "pool": True, "live": False}


def snapshot() -> dict[str, Any]:
    return {
        "jars": len(_JARS),
        "sessions": sum(len(items) for items in _SESSIONS.values()),
        "live": False,
    }
