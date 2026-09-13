"""In-app toasts plus digest-email payloads for the notification center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Notification:
    id: str
    kind: str
    title: str
    body: str
    at: str
    read: bool = False


_ITEMS: list[Notification] = []
_SEQ = 0


def reset() -> None:
    global _SEQ
    _ITEMS.clear()
    _SEQ = 0


def push(*, kind: str, title: str, body: str) -> Notification:
    global _SEQ
    _SEQ += 1
    item = Notification(
        id=f"ntf-{_SEQ}",
        kind=kind,
        title=title,
        body=body,
        at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    _ITEMS.append(item)
    if len(_ITEMS) > 200:
        del _ITEMS[: len(_ITEMS) - 200]
    return item


def inbox(*, unread_only: bool = False) -> list[Notification]:
    rows = [item for item in _ITEMS if (not unread_only or not item.read)]
    return list(reversed(rows))


def mark_read(note_id: str) -> Notification | None:
    for item in _ITEMS:
        if item.id == note_id:
            item.read = True
            return item
    return None


def digest_email() -> dict[str, object]:
    unread = inbox(unread_only=True)
    lines = [f"- {item.title}: {item.body}" for item in unread[:20]]
    return {
        "subject": f"AJAS digest ({len(unread)} unread)" if unread else "AJAS digest (caught up)",
        "text": "\n".join(lines) if lines else "You're caught up.",
        "count": len(unread),
    }
