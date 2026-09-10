"""Review & Decision application service (Backend PRD)."""

from __future__ import annotations

import base64
import json
from datetime import timedelta
from typing import Any, Callable

from app.config import get_settings
from app.review.blobs import InMemoryBlobStore, ReviewBlobStore
from app.review.constants import (
    DECISION_QUEUE,
    DEFAULT_PAGE_SIZE,
    ENRICH_QUEUE,
    IDEMPOTENCY_TTL_HOURS,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    OVERWRITE_WINDOW_HOURS,
    POISON_DEQUEUE,
    SAS_TTL_MINUTES,
)
from app.review.errors import ReviewConflictError, ReviewNotFoundError, ReviewValidationError
from app.review.keys import parse_ts, utc_now
from app.review.models import DecisionEvent, ReviewMatch
from app.review.queues import InMemoryJobQueue, JobQueue
from app.review.store import ReviewStore, get_review_store

Clock = Callable[[], str]


def _page_size(value: int | None) -> int:
    size = DEFAULT_PAGE_SIZE if value is None else value
    if size < MIN_PAGE_SIZE or size > MAX_PAGE_SIZE:
        raise ReviewValidationError(
            f"pageSize must be {MIN_PAGE_SIZE}–{MAX_PAGE_SIZE}",
            path="pageSize",
        )
    return size


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
        offset = int(payload["o"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReviewValidationError("invalid continuation token", path="continuation") from exc
    if offset < 0:
        raise ReviewValidationError("invalid continuation token", path="continuation")
    return offset


def _api_status(status: str) -> str:
    return status.strip().lower()


def _store_status(status: str | None) -> str | None:
    if not status:
        return None
    mapping = {
        "pending": "PENDING",
        "approved": "APPROVED",
        "rejected": "REJECTED",
        "awaiting_decision": "PENDING",
        "awaiting": "PENDING",
        "decided": "DECIDED",
    }
    key = status.strip().lower()
    if key in mapping:
        return mapping[key]
    raise ReviewValidationError("invalid status", path="status")


def _paginate(items: list[Any], *, page_size: int, continuation: str | None) -> tuple[list[Any], str | None]:
    offset = _decode_cursor(continuation)
    page = items[offset : offset + page_size]
    token = _encode_cursor(offset + page_size) if offset + page_size < len(items) else None
    return page, token


def _pending_rank(match: ReviewMatch) -> tuple:
    saved_boost = 1 if match.source == "saved" else 0
    stamp = match.updated_at or match.created_at or ""
    return (saved_boost, stamp)


def _collapse_pending_duplicates(rows: list[ReviewMatch]) -> list[ReviewMatch]:
    groups: dict[tuple[str, str], list[ReviewMatch]] = {}
    for match in rows:
        if match.status != "PENDING":
            continue
        groups.setdefault((match.job_id, match.resume_id), []).append(match)
    keep_ids = set()
    for group in groups.values():
        winner = max(group, key=_pending_rank)
        keep_ids.add(winner.id)
    return [row for row in rows if row.status != "PENDING" or row.id in keep_ids]


def _match_row(match: ReviewMatch) -> dict[str, Any]:
    return {
        "matchId": match.id,
        "userId": match.user_id,
        "jobId": match.job_id,
        "resumeId": match.resume_id,
        "jobTitle": match.job_title,
        "company": match.company,
        "location": match.location,
        "score": match.ai_score,
        "suggestion": match.suggestion,
        "status": _api_status(match.status),
        "source": match.source,
        "createdAt": match.created_at,
        "updatedAt": match.updated_at,
        "queuedAt": match.queued_at,
        "etag": match.etag,
    }


def _match_detail(match: ReviewMatch) -> dict[str, Any]:
    body = _match_row(match)
    body.update(
        {
            "summary": match.summary,
            "why": match.why,
            "highlights": match.highlights_json,
            "summaryBlobUri": match.summary_blob_uri,
            "decidedAt": match.decided_at,
            "latestDecisionId": match.latest_decision_id,
        }
    )
    return body


def _decision_payload(event: DecisionEvent) -> dict[str, Any]:
    return {
        "decisionId": event.id,
        "matchId": event.match_id,
        "userId": event.user_id,
        "decision": event.decision,
        "comment": event.comment,
        "source": event.source,
        "version": event.version,
        "createdAt": event.created_at,
        "actor": event.user_id,
        "supersedesDecisionId": event.supersedes_decision_id,
        "aiScore": event.ai_score,
        "suggestion": event.suggestion,
    }


class ReviewService:
    def __init__(
        self,
        store: ReviewStore | None = None,
        queue: JobQueue | None = None,
        blobs: ReviewBlobStore | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.store = store or get_review_store()
        self.queue = queue or InMemoryJobQueue()
        self.blobs = blobs or InMemoryBlobStore()
        self.clock = clock or utc_now
        self.processed_decisions = 0
        self.poisoned = 0
        self.learning_events: list[dict[str, Any]] = []

    def list_matches(
        self,
        user_id: str,
        *,
        status: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        job_title: str | None = None,
        company: str | None = None,
        location: str | None = None,
        source: str | None = None,
        created_after: str | None = None,
        page_size: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        size = _page_size(page_size)
        if min_score is not None and (min_score < 0 or min_score > 100):
            raise ReviewValidationError("minScore must be between 0 and 100", path="minScore")
        wanted = _store_status(status)
        if wanted == "DECIDED":
            rows = [
                match
                for match in self.store.list_matches(
                    user_id,
                    min_score=min_score,
                    max_score=max_score,
                    job_title=job_title,
                    company=company,
                    location=location,
                    source=source,
                    created_after=created_after,
                )
                if match.status in {"APPROVED", "REJECTED"}
            ]
        else:
            rows = self.store.list_matches(
                user_id,
                status=wanted,
                min_score=min_score,
                max_score=max_score,
                job_title=job_title,
                company=company,
                location=location,
                source=source,
                created_after=created_after,
            )
        visible = {
            row.id for row in _collapse_pending_duplicates(self.store.list_matches(user_id))
        }
        rows = [row for row in rows if row.id in visible]
        page, token = _paginate(rows, page_size=size, continuation=continuation)
        filters = {
            key: value
            for key, value in {
                "status": status,
                "minScore": min_score,
                "jobTitle": job_title,
                "company": company,
                "location": location,
                "source": source,
                "createdAfter": created_after,
            }.items()
            if value not in (None, "")
        }
        self.store.record_audit(user_id=user_id, event_type="VIEW_LIST", payload={"filters": filters})
        if filters:
            self.store.record_audit(user_id=user_id, event_type="FILTER", payload=filters)
        body: dict[str, Any] = {"items": [_match_row(match) for match in page]}
        if token:
            body["continuationToken"] = token
        return body

    def get_match(self, user_id: str, match_id: str) -> dict[str, Any]:
        match = self.store.get_match(match_id, user_id=user_id)
        self.store.record_audit(user_id=user_id, event_type="VIEW_DETAIL", match_id=match.id, payload={})
        degraded = not match.summary or match.highlights_json is None
        if degraded:
            self.store.record_audit(
                user_id=user_id,
                event_type="DEGRADED_VIEW",
                match_id=match.id,
                payload={"missing": [name for name, present in (("summary", match.summary), ("highlights", match.highlights_json)) if not present]},
            )
            self.queue.enqueue(
                get_settings().review_enrich_queue or ENRICH_QUEUE,
                {"eventType": "EnrichRequested", "userId": user_id, "matchId": match.id, "timestamp": self.clock()},
            )
        decision = None
        if match.latest_decision_id:
            events = [event for event in self.store.list_decisions(user_id, match.id) if event.id == match.latest_decision_id]
            if events:
                decision = _decision_payload(events[0])
        settings = get_settings()
        minutes = settings.review_sas_minutes or SAS_TTL_MINUTES
        job_url = self.blobs.sas_url(f"jobs/{user_id}/{match.job_id}", minutes=minutes)
        resume_url = (
            self.blobs.sas_url(f"resumes/{user_id}/{match.resume_id}", minutes=minutes) if match.resume_id else None
        )
        return {
            "match": _match_detail(match),
            "decision": decision,
            "blobs": {"jobUrl": job_url, "resumeUrl": resume_url},
        }

    def decide(
        self,
        user_id: str,
        match_id: str,
        body: dict[str, Any],
        *,
        idempotency_key: str | None,
        etag: str | None,
        ip: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if not idempotency_key:
            raise ReviewValidationError("Idempotency-Key is required", path="Idempotency-Key")
        if not etag:
            raise ReviewValidationError("If-Match is required", path="If-Match")
        decision = body.get("decision")
        if not isinstance(decision, str) or not decision.strip():
            raise ReviewValidationError("decision is required", path="decision")
        comment = body.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise ReviewValidationError("comment must be a string", path="comment")
        if isinstance(comment, str):
            comment = comment.strip() or None
        overwrite = bool(body.get("overwrite"))
        match = self.store.get_match(match_id, user_id=user_id)
        action = decision.strip().lower()
        replay = self._idempotent_replay(user_id, match, action, idempotency_key)
        if replay is not None:
            return replay
        before = match.status
        if match.status in {"APPROVED", "REJECTED"}:
            if not overwrite:
                raise ReviewConflictError("match already has a terminal decision")
            if not self._within_overwrite_window(match.decided_at):
                raise ReviewConflictError("overwrite window has expired")
        store_key = None if self._idempotency_expired(user_id, match.id, idempotency_key) else idempotency_key
        updated, event = self.store.decide(
            user_id,
            match_id,
            action,
            comment=comment,
            overwrite=overwrite,
            etag=etag,
            idempotency_key=store_key,
            source="manual",
        )
        self.store.record_audit(
            user_id=user_id,
            event_type="DECISION",
            match_id=match_id,
            payload={
                "actor": user_id,
                "ip": ip,
                "before": before,
                "after": updated.status,
                "decisionId": event.id,
            },
        )
        self.queue.enqueue(
            get_settings().review_decision_queue or DECISION_QUEUE,
            {
                "eventType": "DecisionCreated",
                "userId": user_id,
                "matchId": updated.id,
                "decisionId": event.id,
                "timestamp": event.decided_at,
            },
        )
        self._log_learning_decision(updated, event, outcome=action)
        return 201, {
            "decisionId": event.id,
            "matchStatus": _api_status(updated.status),
            "version": event.version,
            "occurredAt": event.decided_at,
        }

    def reopen(self, user_id: str, match_id: str) -> dict[str, Any]:
        match = self.store.get_match(match_id, user_id=user_id)
        if match.status == "PENDING":
            raise ReviewConflictError("match is already awaiting a decision")
        updated = self.store.reopen(user_id, match_id)
        return _match_detail(updated)

    def upsert_scored_match(
        self,
        user_id: str,
        *,
        job_id: str,
        resume_id: str,
        job_title: str,
        company: str,
        location: str,
        score: float,
        why: str | None = None,
        source: str = "ai",
        match_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Idempotent Review queue row from a persisted Matching score."""
        if not user_id or not job_id or not resume_id:
            return None
        existing = [
            row
            for row in self.store.list_matches(user_id)
            if row.job_id == job_id and row.resume_id == resume_id
        ]
        suggestion = "approve" if score >= 75 else "reject" if score < 50 else "review"
        pending = [row for row in existing if row.status == "PENDING"]
        if pending:
            same_source = next((row for row in pending if row.source == source), None)
            saved = next((row for row in pending if row.source == "saved"), None)
            target = same_source or saved or pending[0]
            next_source = "saved" if source == "saved" or target.source == "saved" else source
            try:
                updated = self.store.update_pending_match(
                    user_id,
                    target.id,
                    ai_score=score,
                    suggestion=suggestion,
                    why=why,
                    summary=why,
                    job_title=job_title or target.job_title,
                    company=company or target.company,
                    location=location or target.location,
                    source=next_source,
                )
            except ReviewConflictError:
                return _match_row(target)
            for extra in pending:
                if extra.id == target.id:
                    continue
                try:
                    self.store.discard_pending_match(user_id, extra.id)
                except ReviewConflictError:
                    pass
            return _match_row(updated)
        if existing:
            return _match_row(existing[0])
        try:
            row = self.store.create_match(
                user_id,
                job_id=job_id,
                resume_id=resume_id,
                source=source,
                job_title=job_title or job_id,
                company=company or "Unknown",
                location=location or "Remote",
                ai_score=score,
                suggestion=suggestion,
                why=why,
                summary=why,
                match_id=match_id,
            )
        except ReviewConflictError:
            return None
        return _match_row(row)

    def list_saved_jobs(
        self,
        user_id: str,
        *,
        status: str | None = "awaiting_decision",
        page_size: int | None = None,
        continuation: str | None = None,
        sort: str | None = None,
        order: str | None = None,
    ) -> dict[str, Any]:
        wanted = _store_status(status or "awaiting_decision")
        rows = self.store.list_matches(user_id, source="saved")
        visible = {
            row.id for row in _collapse_pending_duplicates(self.store.list_matches(user_id))
        }
        rows = [match for match in rows if match.id in visible]
        if wanted == "PENDING":
            rows = [match for match in rows if match.status == "PENDING"]
        elif wanted == "DECIDED":
            rows = [match for match in rows if match.status in {"APPROVED", "REJECTED"}]
        elif wanted:
            rows = [match for match in rows if match.status == wanted]
        key_name = (sort or "createdAt").strip()
        keys = {
            "createdAt": lambda match: match.created_at or "",
            "jobTitle": lambda match: (match.job_title or "").lower(),
            "company": lambda match: (match.company or "").lower(),
        }
        if key_name not in keys:
            raise ReviewValidationError("sort must be createdAt, jobTitle, or company", path="sort")
        reverse = (order or "desc").strip().lower() != "asc"
        rows = sorted(rows, key=keys[key_name], reverse=reverse)
        size = _page_size(page_size)
        page, token = _paginate(rows, page_size=size, continuation=continuation)
        items = [
            {
                "queueItemId": match.id,
                "jobId": match.job_id,
                "jobTitle": match.job_title,
                "createdAt": match.created_at,
                "status": "awaiting_decision" if match.status == "PENDING" else "decided",
            }
            for match in page
        ]
        body: dict[str, Any] = {"items": items}
        if token:
            body["continuationToken"] = token
        return body

    def list_decisions(
        self,
        user_id: str,
        *,
        match_id: str | None = None,
        job_id: str | None = None,
        decision: str | None = None,
        page_size: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        events = self.store.list_decisions(user_id, match_id)
        if job_id:
            by_id = {match.id: match for match in self.store.list_matches(user_id)}
            events = [
                event
                for event in events
                if (match := by_id.get(event.match_id)) is not None and match.job_id == job_id
            ]
        if decision:
            wanted = decision.strip().lower()
            if wanted not in {"approve", "reject"}:
                raise ReviewValidationError("decision must be approve or reject", path="decision")
            events = [event for event in events if event.decision == wanted]
        events = list(reversed(events))
        size = _page_size(page_size)
        page, token = _paginate(events, page_size=size, continuation=continuation)
        body: dict[str, Any] = {"items": [_decision_payload(event) for event in page]}
        if token:
            body["continuationToken"] = token
        return body

    def history(
        self,
        user_id: str,
        *,
        match_id: str | None = None,
        job_id: str | None = None,
        resume_id: str | None = None,
    ) -> dict[str, Any]:
        provided = [name for name, value in (("matchId", match_id), ("jobId", job_id), ("resumeId", resume_id)) if value]
        if len(provided) != 1:
            raise ReviewValidationError("exactly one of matchId, jobId, or resumeId is required", path="matchId")
        events = self.store.list_decisions(user_id, match_id)
        if job_id or resume_id:
            by_id = {match.id: match for match in self.store.list_matches(user_id)}
            filtered: list[DecisionEvent] = []
            for event in events:
                match = by_id.get(event.match_id)
                if match is None:
                    continue
                if job_id and match.job_id == job_id:
                    filtered.append(event)
                elif resume_id and match.resume_id == resume_id:
                    filtered.append(event)
            events = filtered
        return {"items": [_decision_payload(event) for event in events]}

    def process_decision_event(self, payload: dict[str, Any], *, dequeue_count: int = 1) -> None:
        settings = get_settings()
        limit = settings.review_poison_dequeue or POISON_DEQUEUE
        if dequeue_count > limit:
            self.poisoned += 1
            return
        if payload.get("eventType") != "DecisionCreated":
            raise ReviewValidationError("unsupported eventType")
        if not payload.get("decisionId") or not payload.get("userId"):
            raise ReviewValidationError("decision event missing fields")
        self.processed_decisions += 1

    def process_enrich_event(self, payload: dict[str, Any], *, dequeue_count: int = 1) -> None:
        settings = get_settings()
        limit = settings.review_poison_dequeue or POISON_DEQUEUE
        if dequeue_count > limit:
            self.poisoned += 1
            return
        if payload.get("eventType") != "EnrichRequested":
            raise ReviewValidationError("unsupported eventType")

    def _within_overwrite_window(self, decided_at: str | None) -> bool:
        if not decided_at:
            return True
        settings = get_settings()
        hours = settings.review_overwrite_hours or OVERWRITE_WINDOW_HOURS
        age = parse_ts(self.clock()) - parse_ts(decided_at)
        return age <= timedelta(hours=hours)

    def _match_threshold(self, user_id: str) -> float:
        try:
            from app.settings.mapping import api_threshold
            from app.settings.runtime import try_get_service
            from app.settings.store import get_settings_store

            service = try_get_service()
            store = service.store if service is not None else get_settings_store()
            row = store.get_or_create_settings(user_id)
            return api_threshold(row.match_threshold)
        except Exception:
            return 0.7

    def _log_learning_decision(self, match: ReviewMatch, event: DecisionEvent, *, outcome: str) -> None:
        payload = {
            "eventType": "LearningDecisionLogged",
            "userId": match.user_id,
            "jobId": match.job_id,
            "resumeId": match.resume_id,
            "matchId": match.id,
            "decisionId": event.id,
            "score": event.ai_score,
            "threshold": self._match_threshold(match.user_id),
            "outcome": outcome,
            "occurredAt": event.decided_at,
        }
        self.learning_events.append(payload)
        self.queue.enqueue(get_settings().learning_decisions_queue, payload)
        try:
            from app.learning.runtime import get_service as get_learning_service

            get_learning_service().ingest_event(payload)
        except Exception:
            pass

    def _idempotent_replay(
        self,
        user_id: str,
        match: ReviewMatch,
        decision: str,
        idempotency_key: str,
    ) -> tuple[int, dict[str, Any]] | None:
        events = [
            event
            for event in self.store.list_decisions(user_id, match.id)
            if event.idempotency_key == idempotency_key
        ]
        if not events:
            return None
        event = events[-1]
        settings = get_settings()
        hours = settings.review_overwrite_hours or IDEMPOTENCY_TTL_HOURS
        age = parse_ts(self.clock()) - parse_ts(event.created_at)
        if age > timedelta(hours=hours):
            return None
        if event.decision != decision:
            raise ReviewConflictError("idempotency key reused with a different decision")
        return 200, {
            "decisionId": event.id,
            "matchStatus": _api_status(match.status),
            "version": event.version,
            "occurredAt": event.decided_at,
        }

    def _idempotency_expired(self, user_id: str, match_id: str, idempotency_key: str) -> bool:
        events = [
            event
            for event in self.store.list_decisions(user_id, match_id)
            if event.idempotency_key == idempotency_key
        ]
        if not events:
            return False
        settings = get_settings()
        hours = settings.review_overwrite_hours or IDEMPOTENCY_TTL_HOURS
        age = parse_ts(self.clock()) - parse_ts(events[-1].created_at)
        return age > timedelta(hours=hours)
