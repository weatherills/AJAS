"""Recommended reply times for recruiter threads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.mail.intent import classify_email

DEFAULT_HOURS = {
    "interview": 4,
    "follow_up": 24,
    "generic": 36,
    "rejection": 72,
}


def recommend_followup(*, subject: str, body: str, received_at: datetime | None = None) -> dict[str, object]:
    intent = classify_email(subject=subject, body=body)
    hours = DEFAULT_HOURS.get(str(intent["intent"]), 36)
    start = received_at or datetime.now(timezone.utc)
    due = start + timedelta(hours=hours)
    return {
        "intent": intent["intent"],
        "dueAt": due.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "windowHours": hours,
        "reason": f"Reply to {intent['intent']} mail within {hours} hours.",
    }
