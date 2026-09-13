"""Canned recruiter replies: interested, not a fit, schedule."""

from __future__ import annotations


def recruiter_templates(*, first_name: str, company: str, role: str, job_ref: str = "") -> list[dict[str, str]]:
    person = first_name or "there"
    shop = company or "your team"
    title = role or "the role"
    ref = f" ({job_ref})" if job_ref else ""
    return [
        {
            "id": "interested",
            "label": "Interested",
            "tone": "professional",
            "text": (
                f"Hi {person},\n\nThank you for reaching out about {title} at {shop}{ref}. "
                "I'm interested and can make time this week to talk through next steps.\n\nBest regards"
            ),
        },
        {
            "id": "not_fit",
            "label": "Not a fit",
            "tone": "professional",
            "text": (
                f"Hi {person},\n\nThank you for considering me for {title} at {shop}{ref}. "
                "I'm going to pass on this one, but I appreciate the note and wish you a great search.\n\nBest regards"
            ),
        },
        {
            "id": "schedule",
            "label": "Schedule",
            "tone": "concise",
            "text": (
                f"Hi {person},\n\nThanks — I'm available for {title} at {shop}{ref}. "
                "I can do a call Tuesday–Thursday after 1pm local. What times work for you?\n\nThanks"
            ),
        },
    ]
