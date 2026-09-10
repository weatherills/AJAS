"""Optional Azure Monitor / OTLP export. Local keeps in-process traces."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("ajas")


def export_span(record: dict[str, Any]) -> None:
    connection = (os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or "").strip()
    otlp = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()
    if not connection and not otlp:
        return
    payload = {
        "name": "ajas.trace",
        "target": "azure-monitor" if connection else "otlp",
        "span": {
            "traceId": record.get("traceId"),
            "spanId": record.get("spanId"),
            "name": record.get("name"),
            "elapsedMs": record.get("elapsedMs"),
            "ok": record.get("ok"),
            "error": record.get("error"),
        },
    }
    log.info("ajas.monitor %s", json.dumps(payload, default=str))
