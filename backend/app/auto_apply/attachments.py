"""Resume and cover-letter attachment policy for Auto-Apply."""

from __future__ import annotations

from app.auto_apply.errors import AutoApplyValidationError

RESUME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
COVER_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }
)
MAX_BYTES = 5 * 1024 * 1024
POLICY = {
    "resume": {"contentTypes": sorted(RESUME_TYPES), "maxBytes": MAX_BYTES, "required": True},
    "coverLetter": {"contentTypes": sorted(COVER_TYPES), "maxBytes": MAX_BYTES, "required": False},
}


def validate_attachment(*, kind: str, content_type: str, size: int) -> None:
    allowed = RESUME_TYPES if kind == "resume" else COVER_TYPES
    if content_type not in allowed:
        raise AutoApplyValidationError(f"{kind} file type is not allowed", path=kind)
    if size > MAX_BYTES:
        raise AutoApplyValidationError(f"{kind} must be {MAX_BYTES} bytes or smaller", path=kind)
