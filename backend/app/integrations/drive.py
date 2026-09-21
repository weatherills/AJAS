"""Google Drive resume library: list, permission check, import, version metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from app.flags import feature_enabled
from app.job_sources.keys import utc_now
from app.resumes.errors import FileRejectedError

DRIVE_FLAG = "google_drive"
ALLOWED_MIME = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


class DriveHttp(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str]) -> tuple[int, dict[str, Any] | bytes]: ...


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int
    modified_time: str
    owners: list[str]
    writers: list[str]
    data: bytes = b""
    version: int = 1


class LocalDriveClient:
    def __init__(self) -> None:
        self._files: dict[str, DriveFile] = {}

    def put(self, file: DriveFile) -> DriveFile:
        self._files[file.id] = file
        return file

    def get(self, file_id: str) -> DriveFile | None:
        return self._files.get(file_id)

    def list_files(self) -> list[DriveFile]:
        return list(self._files.values())


def can_access(file: DriveFile, user_email: str) -> bool:
    needle = (user_email or "").strip().lower()
    if not needle:
        return False
    principals = {item.lower() for item in (file.owners + file.writers) if item}
    return needle in principals


def get_file(client: LocalDriveClient, file_id: str) -> DriveFile | None:
    return client.get(file_id)


def list_library(client: LocalDriveClient, *, user_email: str) -> list[dict[str, Any]]:
    out = []
    for item in client.list_files():
        if not can_access(item, user_email):
            continue
        out.append(_meta(item))
    return out


def _meta(item: DriveFile) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "mimeType": item.mime_type,
        "size": item.size,
        "modifiedTime": item.modified_time,
        "version": item.version,
        "owners": list(item.owners),
    }


def import_resume(
    *,
    user_id: str,
    user_email: str,
    file_id: str,
    client: LocalDriveClient,
    resume_service: Any,
) -> dict[str, Any]:
    if not feature_enabled(DRIVE_FLAG):
        return {"enabled": False, "reason": "flag_off"}
    item = client.get(file_id)
    if item is None:
        return {"enabled": True, "reason": "not_found", "fileId": file_id}
    if not can_access(item, user_email):
        return {"enabled": True, "reason": "forbidden", "fileId": file_id}
    if item.mime_type not in ALLOWED_MIME:
        return {"enabled": True, "reason": "unsupported_type", "fileId": file_id, "mimeType": item.mime_type}
    try:
        resume = resume_service.upload(
            user_id=user_id,
            filename=item.name,
            content_type=item.mime_type,
            data=item.data,
        )
    except FileRejectedError as exc:
        return {"enabled": True, "reason": "rejected", "error": str(exc), "fileId": file_id}
    return {
        "enabled": True,
        "reason": "ok",
        "fileId": file_id,
        "resumeId": getattr(resume, "id", None),
        "filename": item.name,
        "version": item.version,
        "checksumSource": "drive",
        "modifiedTime": item.modified_time,
        "retrievedAt": utc_now(),
    }


def seed_pdf(*, name: str = "resume.pdf", owner: str, data: bytes | None = None) -> DriveFile:
    payload = data if data is not None else b"%PDF-1.4 demo resume"
    return DriveFile(
        id=f"drv-{uuid4().hex[:10]}",
        name=name,
        mime_type="application/pdf",
        size=len(payload),
        modified_time=utc_now(),
        owners=[owner],
        writers=[owner],
        data=payload,
        version=1,
    )
