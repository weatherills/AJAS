"""Audit log for automated actions (who / when / what)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.mail.pii import redact_pii
from app.matching.keys import utc_now

log = logging.getLogger("ajas")

_EVENTS: list[dict[str, Any]] = []


def record_action(*, actor: str, action: str, target: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "at": utc_now(),
        "actor": actor,
        "action": action,
        "target": target,
        "detail": detail or {},
    }
    _EVENTS.append(event)
    if len(_EVENTS) > 500:
        del _EVENTS[: len(_EVENTS) - 500]
    log.info("ajas.audit %s", redact_pii(json.dumps(event, default=str)))
    return event


def recent_actions(limit: int = 50) -> list[dict[str, Any]]:
    return list(_EVENTS[-limit:])
