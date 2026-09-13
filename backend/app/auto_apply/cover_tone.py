"""Cover-letter tone/style presets."""

from __future__ import annotations

TONES = {
    "concise": {
        "label": "Concise",
        "opener": "I'm applying for {role} at {company}.",
        "closer": "Happy to share more on a short call.",
    },
    "enthusiastic": {
        "label": "Enthusiastic",
        "opener": "I'm excited to apply for {role} at {company} — the work lines up with what I enjoy building.",
        "closer": "I'd love the chance to contribute and am ready to jump in.",
    },
    "formal": {
        "label": "Formal",
        "opener": "Please accept this application for the {role} position at {company}.",
        "closer": "Thank you for your time and consideration.",
    },
}


def render_cover(*, role: str, company: str, name: str, tone: str = "concise", body: str = "") -> dict[str, str]:
    preset = TONES.get((tone or "concise").lower(), TONES["concise"])
    opener = preset["opener"].format(role=role or "this role", company=company or "your team")
    closer = preset["closer"]
    middle = (body or "My background matches the posting.").strip()
    letter = f"Dear hiring team,\n\n{opener} {middle}\n\n{closer}\n\nSincerely,\n{name or 'Candidate'}\n"
    return {"tone": tone if tone in TONES else "concise", "label": preset["label"], "text": letter}
