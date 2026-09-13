"""Strip signature blocks and quoted reply text from recruiter mail."""

from __future__ import annotations

_QUOTE_MARKERS = ("wrote:", "original message", "forwarded message")


def strip_quoted(text: str | None) -> str:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        lower = stripped.lower()
        if stripped.startswith(">"):
            break
        if lower in {"--", "—", "__"} or lower.startswith("-- "):
            break
        if lower.startswith("sent from my") or lower.startswith("best regards") or lower.startswith("kind regards"):
            break
        if any(marker in lower for marker in _QUOTE_MARKERS):
            break
        lines.append(raw.rstrip())
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()
