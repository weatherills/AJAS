"""Multi-step apply form state machine (core). Never skips CAPTCHA/HITL."""

from __future__ import annotations

from typing import Any
from app.auto_apply.captcha import apply_gate

STATES = ("draft", "profile", "questions", "review", "submit", "needs_manual", "done")


def next_state(current: str, event: str, *, payload: Any = None) -> str:
    cur = current if current in STATES else "draft"
    if apply_gate(payload) == "needs_manual":
        return "needs_manual"
    transitions = {
        ("draft", "start"): "profile",
        ("profile", "next"): "questions",
        ("questions", "next"): "review",
        ("review", "submit"): "submit",
        ("submit", "ok"): "done",
        ("submit", "fail"): "needs_manual",
        ("needs_manual", "resume"): "review",
    }
    return transitions.get((cur, event), cur)
