"""Role-specific cover letter prompt templates."""

from __future__ import annotations

from app.auto_apply.cover_tone import render_cover

ROLE_BODIES = {
    "backend": "I focus on APIs, data, and reliable services.",
    "frontend": "I care about accessible UI, performance, and design systems.",
    "data": "I build pipelines, models, and decision-ready metrics.",
    "pm": "I shape problems, sequence bets, and ship with engineering partners.",
}


def render_role_cover(*, role_family: str, role: str, company: str, name: str, tone: str = "concise") -> dict[str, str]:
    family = (role_family or "backend").lower()
    body = ROLE_BODIES.get(family, ROLE_BODIES["backend"])
    letter = render_cover(role=role, company=company, name=name, tone=tone, body=body)
    return {**letter, "roleFamily": family if family in ROLE_BODIES else "backend"}
