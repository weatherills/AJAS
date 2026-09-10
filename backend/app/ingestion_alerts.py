"""Outbound ingestion alerts. Demo-seed skips must not page."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

log = logging.getLogger("ajas")

_last_alert: str | None = None


def maybe_alert(*, failure_count: int, events: list[dict[str, Any]] | None = None) -> bool:
    if failure_count < 3:
        return False
    rows = events or []
    if rows and all((item.get("kind") == "skip") or item.get("demo_seed") for item in rows if item.get("kind") in {"error", "rate_limited", "skip"}):
        return False
    payload = {"alert": True, "failureCount": failure_count, "source": "ajas.ingestion"}
    key = json.dumps(payload, sort_keys=True)
    global _last_alert
    if _last_alert == key:
        return True
    _last_alert = key
    log.warning("ajas.ingestion.alert %s", json.dumps(payload))
    webhook = (os.environ.get("INGESTION_ALERT_WEBHOOK") or "").strip()
    if not webhook:
        try:
            from app.config import get_settings

            webhook = (get_settings().ingestion_alert_webhook or "").strip()
        except Exception:
            webhook = ""
    if webhook:
        try:
            req = urllib.request.Request(
                webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as exc:
            log.warning("ajas.ingestion.alert webhook failed: %s", exc)
    return True
