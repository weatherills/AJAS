"""Structured request logging for Settings and Review HTTP APIs."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.request_context import current_request_id

log = logging.getLogger("ajas")


def log_request(
    *,
    feature: str,
    route: str,
    method: str,
    status: int,
    user_id: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "feature": feature,
        "route": route,
        "method": method,
        "status": status,
        "user_id": user_id or "-",
        "request_id": current_request_id() or "-",
    }
    if extra:
        payload.update(extra)
    if error:
        payload["error"] = error
        log.warning("ajas.request %s", json.dumps(payload, default=str))
        return
    log.info("ajas.request %s", json.dumps(payload, default=str))


def log_exception(feature: str, route: str, exc: Exception) -> None:
    log.exception("ajas.error feature=%s route=%s error=%s", feature, route, exc)
