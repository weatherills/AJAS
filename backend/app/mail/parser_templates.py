"""Invite / reject / neutral recruiter email templates for parser tests."""

from __future__ import annotations

TEMPLATES = {
    "invite": {
        "subject": "Interview invitation for Staff Engineer",
        "body": "We would like to schedule a 45-minute interview next week. Are you free Tuesday afternoon?",
    },
    "reject": {
        "subject": "Update on your application",
        "body": "Thank you for applying. We are not moving forward at this time.",
    },
    "neutral": {
        "subject": "Thanks for chatting",
        "body": "Great connecting today. We will follow up if there is another role that fits.",
    },
}
