"""Product Slack notifications: matches, applications, recruiter replies."""

from __future__ import annotations

from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from app.flags import feature_enabled
from app.notify import Notification, push as notify_push

SLACK_FLAG = "slack_notify"

CHANNELS = {
    "match": "#ajas-matches",
    "new_match": "#ajas-matches",
    "application": "#ajas-apply",
    "submitted": "#ajas-apply",
    "recruiter_reply": "#ajas-mail",
    "mail": "#ajas-mail",
    "ingest_failure": "#ajas-ops",
    "default": "#ajas-product",
}


class SlackHttp(Protocol):
    def post(self, url: str, payload: dict[str, Any]) -> tuple[int, str]: ...


class UrllibSlackHttp:
    def post(self, url: str, payload: dict[str, Any]) -> tuple[int, str]:
        body = json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json", "User-Agent": "AJAS-slack/1.0"})
        try:
            with urlopen(req, timeout=10) as resp:
                return int(getattr(resp, "status", 200)), resp.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            return int(exc.code), raw.decode("utf-8", errors="replace")
        except URLError as exc:
            raise TimeoutError(str(exc.reason or exc)) from exc


class MemorySlackHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, payload: dict[str, Any]) -> tuple[int, str]:
        self.calls.append((url, payload))
        return 200, "ok"


def route_channel(kind: str) -> str:
    return CHANNELS.get((kind or "").strip().lower(), CHANNELS["default"])


def format_event(*, kind: str, title: str, body: str, channel: str | None = None) -> dict[str, Any]:
    dest = channel or route_channel(kind)
    color = {
        "match": "good",
        "new_match": "good",
        "application": "#439FE0",
        "submitted": "#439FE0",
        "recruiter_reply": "warning",
        "ingest_failure": "danger",
    }.get(kind, "#439FE0")
    return {
        "channel": dest,
        "text": f"{title}: {body}",
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "kind", "value": kind, "short": True},
                    {"title": "title", "value": title, "short": False},
                ],
            }
        ],
    }


def post_webhook(
    url: str,
    payload: dict[str, Any],
    *,
    http: SlackHttp | None = None,
) -> dict[str, Any]:
    if not url:
        return {"ok": False, "reason": "not_configured"}
    client = http or UrllibSlackHttp()
    status, body = client.post(url, payload)
    return {"ok": 200 <= status < 300, "status": status, "body": body, "channel": payload.get("channel")}


def notify_event(
    *,
    kind: str,
    title: str,
    body: str,
    webhook_url: str = "",
    http: SlackHttp | None = None,
    mirror_in_app: bool = True,
) -> dict[str, Any]:
    if not feature_enabled(SLACK_FLAG):
        return {"enabled": False, "reason": "flag_off"}
    payload = format_event(kind=kind, title=title, body=body)
    posted = post_webhook(webhook_url, payload, http=http) if webhook_url else {"ok": False, "reason": "not_configured"}
    note = None
    if mirror_in_app:
        note = notify_push(kind=kind, title=title, body=body)
    return {
        "enabled": True,
        "reason": "ok" if posted.get("ok") or posted.get("reason") == "not_configured" else "webhook_failed",
        "payload": payload,
        "webhook": posted,
        "notificationId": getattr(note, "id", None),
    }


def mirror_notification(item: Notification, *, webhook_url: str = "", http: SlackHttp | None = None) -> dict[str, Any]:
    return notify_event(kind=item.kind, title=item.title, body=item.body, webhook_url=webhook_url, http=http, mirror_in_app=False)
