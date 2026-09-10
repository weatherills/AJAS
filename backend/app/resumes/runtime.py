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
        from app.resumes.queueing import AzureParseQueue, InMemoryParseQueue
        from app.resumes.store import get_resume_store

        settings = get_settings()
        # In-memory resume rows live in this process. Azurite queue workers cannot
        # see them, so parse locally unless Cosmos is configured.
        use_local_queue = not (settings.cosmos_connection_string or "").strip()
        queue = InMemoryParseQueue() if use_local_queue else AzureParseQueue()
        service = ResumeService(
            store=get_resume_store(),
            blobs=AzureResumeBlobStore(),
            queue=queue,
            parser=default_parser(),
        )
        if use_local_queue:
            # Same-process parse: fail the job immediately instead of raising for
            # Azure queue retries (those would 500 the upload request).
            queue.handler = lambda msg: service.process_parse_job(msg, dequeue_count=3)
            from app.resumes.demo import seed_demo_resume
            from app.resumes.memory import InMemoryResumeStore

            if isinstance(service.store, InMemoryResumeStore):
                seed_demo_resume(service.store)
        _service = service
    return _service


def set_service(service: ResumeService | None) -> None:
    global _service
    _service = service
