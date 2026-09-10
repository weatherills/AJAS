"""Structured crawl observability events (start/finish/error/rate-limited)."""

from __future__ import annotations

import logging
from typing import Any

from app.job_sources.keys import utc_now

log = logging.getLogger("ajas")


class CrawlEventLog:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        event = {"kind": kind, "at": utc_now(), **fields}
        self.events.append(event)
        if len(self.events) > 200:
            del self.events[: len(self.events) - 200]
        log.info("ajas.source.event %s", event)
        return event
