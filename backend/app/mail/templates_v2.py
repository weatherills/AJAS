"""Reply templates with variable placeholders and a preview renderer."""

from __future__ import annotations

import re

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

TEMPLATES = {
    "interested": "Hi {{first_name}}, thanks for reaching out about {{role}} at {{company}}. I'm interested.",
    "not_fit": "Hi {{first_name}}, thank you for considering me for {{role}} at {{company}}. I'll pass this time.",
    "follow_up": "Hi {{first_name}}, just checking in on {{role}} at {{company}}. Happy to share anything else you need.",
}


def available_placeholders(template: str) -> list[str]:
    return list(dict.fromkeys(_PLACEHOLDER.findall(template or "")))


def render_template(template: str, values: dict[str, str]) -> dict[str, object]:
    missing: list[str] = []

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values and str(values[key]).strip():
            return str(values[key])
        missing.append(key)
        return match.group(0)

    preview = _PLACEHOLDER.sub(repl, template or "")
    return {
        "preview": preview,
        "placeholders": available_placeholders(template),
        "missing": list(dict.fromkeys(missing)),
        "complete": not missing,
    }


def preset(name: str, values: dict[str, str]) -> dict[str, object]:
    text = TEMPLATES.get(name, TEMPLATES["interested"])
    rendered = render_template(text, values)
    rendered["id"] = name if name in TEMPLATES else "interested"
    return rendered
