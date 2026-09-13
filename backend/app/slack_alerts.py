"""Slack-compatible alert payloads for SLO breaches."""

from __future__ import annotations

from typing import Any


def slack_payload(alert: dict[str, Any], *, channel: str = "#ajas-ops") -> dict[str, Any]:
    route = alert.get("route") or alert.get("metric") or "unknown"
    return {
        "channel": channel,
        "text": f"SLO breach: {route} p95={alert.get('p95Ms')} budget={alert.get('budgetMs')}",
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {"title": "route", "value": str(route), "short": True},
                    {"title": "p95Ms", "value": str(alert.get("p95Ms")), "short": True},
                ],
            }
        ],
    }


def should_notify(alert: dict[str, Any]) -> bool:
    return bool(alert) and alert.get("ok") is False
