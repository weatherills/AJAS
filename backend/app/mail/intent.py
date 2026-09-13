"""Classify recruiter mail as interview, rejection, or generic follow-up."""

from __future__ import annotations

import re

_INTERVIEW = re.compile(
    r"\b(interview|phone screen|onsite|on-site|loop|availability|calendar invite|meet with)\b",
    re.I,
)
_REJECT = re.compile(
    r"\b(unfortunately|not moving forward|other candidates|reject|not selected|no longer being considered)\b",
    re.I,
)
_FOLLOW = re.compile(r"\b(following up|checking in|any update|touching base|circle back)\b", re.I)


def classify_email(*, subject: str = "", body: str = "") -> dict[str, object]:
    hay = f"{subject}\n{body}"
    if _REJECT.search(hay):
        intent = "rejection"
        confidence = 0.86
    elif _INTERVIEW.search(hay):
        intent = "interview"
        confidence = 0.9
    elif _FOLLOW.search(hay):
        intent = "follow_up"
        confidence = 0.72
    else:
        intent = "generic"
        confidence = 0.4
    return {"intent": intent, "confidence": confidence, "subject": subject[:180]}
