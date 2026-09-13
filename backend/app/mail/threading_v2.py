"""Reliable email thread IDs from Graph conversationId, Message-ID, and In-Reply-To."""

from __future__ import annotations

import hashlib
import re

_ANGLE = re.compile(r"<([^>]+)>")


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    match = _ANGLE.search(text)
    return (match.group(1) if match else text).strip().lower()


def thread_id(*, conversation_id: str | None = None, message_id: str | None = None, in_reply_to: str | None = None, references: str | None = None) -> str:
    if conversation_id and conversation_id.strip():
        return f"graph:{conversation_id.strip()}"
    parent = _clean(in_reply_to) or _clean((references or "").split()[0] if references else "")
    if parent:
        return f"rfc:{parent}"
    own = _clean(message_id)
    if own:
        return f"rfc:{own}"
    digest = hashlib.sha1(f"{message_id}|{in_reply_to}|{references}".encode()).hexdigest()[:12]
    return f"anon:{digest}"
