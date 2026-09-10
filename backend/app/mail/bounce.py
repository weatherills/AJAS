"""Detect bounce / deferral notices so threads can surface delivery status."""

from __future__ import annotations

import re

BOUNCE_FROM = re.compile(
    r"(mailer-daemon|postmaster|noreply-bounce|bounces@)",
    re.I,
)
BOUNCE_SUBJECT = re.compile(
    r"(undeliverable|delivery status notification|returned mail|failure notice|mailbox unavailable)",
    re.I,
)
DEFER_SUBJECT = re.compile(r"(deferred|try again later|temporarily delayed)", re.I)


def classify_delivery(from_address: str, subject: str, body_text: str = "") -> str | None:
    blob = f"{from_address} {subject} {body_text[:400]}"
    if BOUNCE_FROM.search(from_address or "") or BOUNCE_SUBJECT.search(subject or "") or "5.1.1" in blob:
        return "bounced"
    if DEFER_SUBJECT.search(subject or "") or "4.4.1" in blob:
        return "deferred"
    return None


def thread_fingerprint(subject: str, participants: list[str]) -> tuple[str, tuple[str, ...]]:
    normalized = re.sub(r"^(re|fwd|fw)\s*:\s*", "", (subject or "").strip(), flags=re.I)
    normalized = re.sub(r"\s+", " ", normalized).lower()
    people = tuple(sorted({item.strip().lower() for item in participants if item and "@" in item}))
    return normalized, people
