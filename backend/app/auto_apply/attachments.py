"""Resume and cover-letter attachment policy for Auto-Apply.

Backend PRD: PDF/DOCX up to 5 MB, virus scan must pass, and text must be
extractable for resume/DOCX/PDF payloads when bytes are supplied for parse.
"""

from __future__ import annotations

from app.auto_apply.errors import AutoApplyValidationError
from app.mail.scan import scan_attachment
from app.resumes.errors import FileRejectedError
from app.resumes.files import DOCX, PDF, extract_text

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
TEXT_TYPES = frozenset({"text/plain", "text/markdown"})
POLICY = {
    "resume": {
        "contentTypes": sorted(RESUME_TYPES),
        "maxBytes": MAX_BYTES,
        "required": True,
        "virusScan": True,
        "textExtractable": True,
    },
    "coverLetter": {
        "contentTypes": sorted(COVER_TYPES),
        "maxBytes": MAX_BYTES,
        "required": False,
        "virusScan": True,
        "textExtractable": True,
    },
}


def validate_attachment(
    *,
    kind: str,
    content_type: str,
    size: int,
    data: bytes | None = None,
    filename: str = "",
    require_text: bool = False,
) -> None:
    allowed = RESUME_TYPES if kind == "resume" else COVER_TYPES
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in allowed:
        raise AutoApplyValidationError(f"{kind} file type is not allowed", path=kind)
    if size > MAX_BYTES or (data is not None and len(data) > MAX_BYTES):
        raise AutoApplyValidationError(f"{kind} must be {MAX_BYTES} bytes or smaller", path=kind)
    if data is None:
        return
    inspect_attachment_bytes(
        kind=kind,
        content_type=mime,
        data=data,
        filename=filename,
        require_text=require_text,
    )


def inspect_attachment_bytes(
    *,
    kind: str,
    content_type: str,
    data: bytes,
    filename: str = "",
    require_text: bool = False,
) -> str:
    """Virus-scan bytes. When require_text is set, PDF/DOCX/text must yield text."""
    if not data:
        raise AutoApplyValidationError(f"{kind} file is empty", path=kind)
    name = filename or f"{kind}.bin"
    result = scan_attachment(data, file_name=name)
    if not result.clean:
        raise AutoApplyValidationError("File failed antivirus scan", path=kind)
    if not require_text:
        return ""
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in TEXT_TYPES or name.lower().endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace").strip()
        if not text:
            raise AutoApplyValidationError("Attachment has no extractable text", path=kind)
        return text
    if mime not in {PDF, DOCX}:
        raise AutoApplyValidationError(f"{kind} file type is not allowed", path=kind)
    try:
        text = extract_text(name, mime, data).strip()
    except FileRejectedError as exc:
        raise AutoApplyValidationError(str(exc), path=kind) from exc
    except Exception as exc:
        raise AutoApplyValidationError("Could not extract text from attachment", path=kind) from exc
    if not text:
        raise AutoApplyValidationError("Attachment has no extractable text", path=kind)
    return text
