"""Build a downloadable manual application zip."""

from __future__ import annotations

import io
import json
import zipfile


def build_manual_package_zip(
    *,
    deep_link: str | None,
    resume_id: str | None,
    cover_text: str | None,
    fields: dict[str, str],
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.txt",
            "AJAS manual application package.\n"
            "Open apply-link.txt in a browser, attach the resume, and paste cover-letter.txt if present.\n",
        )
        zf.writestr("apply-link.txt", (deep_link or "").strip() + "\n")
        zf.writestr("resume-id.txt", (resume_id or "resume-active") + "\n")
        zf.writestr("fields.json", json.dumps(fields, indent=2, sort_keys=True) + "\n")
        if cover_text and cover_text.strip():
            zf.writestr("cover-letter.txt", cover_text.strip() + "\n")
    return buf.getvalue()
