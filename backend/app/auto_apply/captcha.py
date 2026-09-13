"""Pluggable CAPTCHA detection with a human-in-the-loop stub.

AJAS never solves or bypasses CAPTCHAs (Auto-Apply PRD). Detection routes the
apply to needs_manual / HITL.
"""

from __future__ import annotations

import re
from typing import Any

_CAPTCHA = re.compile(r"captcha|hcaptcha|recaptcha|cf-challenge|turnstile", re.I)


def detect(payload: Any) -> dict[str, object]:
    text = payload if isinstance(payload, str) else str(payload or "")
    hit = bool(_CAPTCHA.search(text))
    return {
        "captcha": hit,
        "action": "needs_manual" if hit else "continue",
        "hitl": hit,
        "bypass": False,
    }


def apply_gate(payload: Any) -> str:
    """Return the next apply state. Never returns a solved-captcha path."""
    return str(detect(payload)["action"])
