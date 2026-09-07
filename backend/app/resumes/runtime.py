"""Process-wide ResumeService used by HTTP and queue triggers."""

from __future__ import annotations

from app.resumes.service import ResumeService

_service: ResumeService | None = None


def get_service() -> ResumeService:
    global _service
    if _service is None:
        from app.config import get_settings
        from app.resumes.blobs import AzureResumeBlobStore
        from app.resumes.parser import default_parser
        from app.resumes.queueing import default_queue
        from app.resumes.store import get_resume_store

        settings = get_settings()
        _ = settings
        _service = ResumeService(
            store=get_resume_store(),
            blobs=AzureResumeBlobStore(),
            queue=default_queue(),
            parser=default_parser(),
        )
    return _service


def set_service(service: ResumeService | None) -> None:
    global _service
    _service = service
