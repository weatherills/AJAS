"""Map IMAP/system mailbox labels onto internal AJAS thread states."""

from __future__ import annotations

LABEL_STATES = {
    "inbox": "open",
    "\\inbox": "open",
    "sent": "sent",
    "\\sent": "sent",
    "drafts": "draft",
    "\\drafts": "draft",
    "junk": "spam",
    "spam": "spam",
    "trash": "deleted",
    "deleted": "deleted",
    "archive": "archived",
    "ajas/applied": "applied",
    "ajas/interview": "interview",
    "ajas/reject": "rejected",
    "ajas/followup": "follow_up",
}


def map_label(label: str) -> str:
    key = (label or "").strip().lower()
    return LABEL_STATES.get(key, "open")


def map_labels(labels: list[str]) -> dict[str, str]:
    mapped = {label: map_label(label) for label in labels}
    priority = ["rejected", "interview", "applied", "follow_up", "spam", "deleted", "draft", "sent", "archived", "open"]
    states = list(mapped.values())
    current = next((state for state in priority if state in states), "open")
    return {"states": mapped, "current": current}
