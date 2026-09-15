"""Resume Management application service (Backend PRD)."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import get_settings
from app.metrics import increment
from app.resumes.blobs import InMemoryBlobStore, ResumeBlobStore, scan_antivirus
from app.resumes.constants import (
    HEURISTIC_SOURCE_VERSION,
    PARSE_BACKOFF_SECONDS,
)
from app.resumes.errors import (
    FileRejectedError,
    ResumeNotFoundError,
    ResumeRateLimitedError,
)
from app.resumes.files import extract_text, sniff_mime, validate_upload
from app.resumes.mapping import snapshot_from_patch
from app.resumes.memory import InMemoryResumeStore
from app.resumes.models import Resume, ResumeParseEvent, RunResumeSelection
from app.resumes.parser import HeuristicResumeParser, ResumeParser
from app.resumes.queueing import InMemoryParseQueue, ParseQueue
from app.resumes.store import ResumeStore
from app.resumes.validation import compute_validated


class ResumeService:
    def __init__(
        self,
        store: ResumeStore | None = None,
        blobs: ResumeBlobStore | None = None,
        queue: ParseQueue | None = None,
        parser: ResumeParser | None = None,
    ) -> None:
        self.store = store or InMemoryResumeStore()
        self.blobs = blobs or InMemoryBlobStore()
        self.queue = queue or InMemoryParseQueue()
        self.parser = parser or HeuristicResumeParser()

    def upload(self, *, user_id: str, filename: str, content_type: str | None, data: bytes) -> Resume:
        settings = get_settings()
        mime_type = sniff_mime(filename, content_type)
        scan_antivirus(data, mime_type=mime_type)
        validate_upload(filename=filename, mime_type=mime_type, data=data)
        self._enforce_upload_limits(user_id, settings)
        checksum = hashlib.sha256(data).hexdigest()
        resume_id = str(uuid4())
        blob_path = self.blobs.put(
            user_id=user_id,
            resume_id=resume_id,
            filename=filename,
            data=data,
            mime_type=mime_type,
        )
        resume = self.store.create_resume(
            user_id=user_id,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(data),
            blob_uri=blob_path,
            checksum_sha256=checksum,
            resume_id=resume_id,
        )
        self.store.record_status(user_id, resume.id, "queued")
        self.queue.enqueue(
            {
                "resumeId": resume.id,
                "ownerUserId": user_id,
                "blobPath": blob_path,
                "attempt": 1,
                "backoffSeconds": PARSE_BACKOFF_SECONDS[0],
            }
        )
        increment("resume.upload")
        return self.store.get_resume(user_id, resume.id)

    def list_resumes(self, user_id: str, *, cursor: str | None, limit: int) -> dict:
        limit = max(1, min(limit, 100))
        rows = self.store.list_resumes(user_id)
        if cursor:
            ids = [row.id for row in rows]
            if cursor in ids:
                rows = rows[ids.index(cursor) + 1 :]
        page = rows[:limit]
        next_cursor = page[-1].id if len(page) == limit and rows[limit:] else None
        return {"items": page, "nextCursor": next_cursor}

    def get(self, user_id: str, resume_id: str) -> Resume:
        resume = self.store.get_resume(user_id, resume_id)
        if resume.is_deleted:
            raise ResumeNotFoundError(resume_id)
        return resume

    def preview_url(self, user_id: str, resume_id: str) -> str:
        resume = self.get(user_id, resume_id)
        return self.blobs.sas_url(resume.blob_uri, minutes=10)

    def patch(self, user_id: str, resume_id: str, body: dict) -> Resume:
        resume = self.get(user_id, resume_id)
        snapshot = snapshot_from_patch(resume, body)
        updated = self.store.replace_structured_data(
            user_id,
            resume_id,
            snapshot,
            last_edited_by=user_id,
            source="manual",
        )
        if updated.processing_status == "failed" and compute_validated(snapshot):
            updated = self.store.record_status(user_id, resume_id, "parsed")
            updated = self.store.get_resume(user_id, resume_id)
        increment("resume.edit")
        self._notify_matching(user_id)
        return updated

    def retry_parse(self, user_id: str, resume_id: str) -> Resume:
        resume = self.get(user_id, resume_id)
        self.store.record_status(user_id, resume_id, "queued", parsing_error=None)
        self.queue.enqueue(
            {
                "resumeId": resume.id,
                "ownerUserId": user_id,
                "blobPath": resume.blob_uri,
                "attempt": 1,
                "backoffSeconds": PARSE_BACKOFF_SECONDS[0],
            }
        )
        return self.store.get_resume(user_id, resume_id)

    def delete(self, user_id: str, resume_id: str) -> None:
        try:
            resume = self.store.get_resume(user_id, resume_id)
        except ResumeNotFoundError:
            return
        if resume.is_deleted:
            return
        self.store.soft_delete(user_id, resume_id)
        self.store.clear_selections_for_resume(user_id, resume_id)
        # Original blob is retained 30 days (Backend PRD). Adapter still exposes delete.
        self._notify_matching(user_id)

    def list_audit(self, user_id: str, resume_id: str) -> list[ResumeParseEvent]:
        self.get(user_id, resume_id)
        return self.store.list_parse_events(resume_id)

    def set_active(self, user_id: str, run_id: str, resume_id: str) -> RunResumeSelection:
        selection = self.store.set_run_selection(run_id=run_id, user_id=user_id, resume_id=resume_id)
        self._notify_matching(user_id)
        return selection

    def get_active(self, user_id: str, run_id: str) -> RunResumeSelection:
        selection = self.store.get_run_selection(run_id)
        if selection is None or selection.user_id != user_id:
            raise ResumeNotFoundError(run_id)
        return selection

    def set_user_active(self, user_id: str, resume_id: str) -> Resume:
        updated = self.store.set_user_active(user_id, resume_id)
        self._notify_matching(user_id)
        return updated

    def get_user_active(self, user_id: str) -> Resume:
        resume = self.store.get_user_active(user_id)
        if resume is None or resume.is_deleted:
            raise ResumeNotFoundError("active")
        return resume

    def process_parse_job(self, message: dict, *, dequeue_count: int = 1) -> None:
        resume_id = message["resumeId"]
        user_id = message["ownerUserId"]
        blob_path = message["blobPath"]
        resume = self.store.get_resume(user_id, resume_id)
        if resume.is_deleted:
            return
        self.store.record_status(user_id, resume_id, "parsing")
        started = time.perf_counter()
        try:
            data = self.blobs.get(blob_path)
            text = extract_text(resume.original_filename, resume.mime_type, data)
            snapshot = self.parser.parse(resume_id=resume_id, text=text)
            source_version = getattr(self.parser, "source_version", HEURISTIC_SOURCE_VERSION)
            self.store.record_parse_success(
                user_id,
                resume_id,
                snapshot,
                parsing_confidence=70,
                source_version=source_version,
            )
            increment("resume.parse.ok")
            increment("resume.parse.ms", (time.perf_counter() - started) * 1000)
            self._notify_matching(user_id)
        except Exception as exc:
            increment("resume.parse.fail")
            # Two retries after the first attempt (dequeue_count 1,2,3) then fail.
            if dequeue_count >= 3:
                self.store.record_status(
                    user_id,
                    resume_id,
                    "failed",
                    parsing_error=_safe_parse_error(exc),
                )
                return
            message["attempt"] = dequeue_count + 1
            message["backoffSeconds"] = _backoff_seconds(dequeue_count)
            raise

    def _enforce_upload_limits(self, user_id: str, settings) -> None:
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = 0
        in_flight = 0
        for resume in self.store.list_resumes(user_id):
            created = _parse_ts(resume.created_at)
            if created >= hour_ago:
                recent += 1
            if resume.processing_status in {"uploaded", "queued", "parsing"}:
                in_flight += 1
        if recent >= settings.resume_upload_rate_per_hour:
            raise ResumeRateLimitedError("Upload rate limit exceeded (30 per hour)")
        if in_flight >= settings.resume_max_concurrent_parses:
            raise ResumeRateLimitedError("Too many concurrent parses (max 5)")

    def _notify_matching(self, user_id: str) -> None:
        try:
            from app.matching.runtime import try_get_service

            matching = try_get_service()
            if matching is not None:
                matching.invalidate_list_cache(user_id)
        except Exception:
            return


def _backoff_seconds(dequeue_count: int) -> int:
    index = min(max(dequeue_count, 1), len(PARSE_BACKOFF_SECONDS)) - 1
    return PARSE_BACKOFF_SECONDS[index]


def _parse_ts(value: str) -> datetime:
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _safe_parse_error(exc: Exception) -> str:
    if isinstance(exc, FileRejectedError):
        return str(exc)
    return "Resume parsing failed. Please try again or edit the resume manually."
