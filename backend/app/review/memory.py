"""In-memory Review store — the rule engine Cosmos hydrates into."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.review.constants import (
    DECISIONS,
    DECISION_SOURCES,
    DEFAULT_LOCK_SECONDS,
    MATCH_SOURCES,
    MATCH_STATUSES,
    MAX_COMMENT_CHARS,
    SUGGESTIONS,
)
from app.review.errors import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewPreconditionError,
    ReviewValidationError,
)
from app.review.keys import is_lock_expired, lock_until, next_etag, parse_ts, utc_now
from app.review.models import AuditEvent, DecisionEvent, ReviewMatch, new_id


def _require_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewValidationError(f"{field_name} is required", path=field_name)
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewValidationError("value must be a string or null")
    stripped = value.strip()
    return stripped or None


def _validate_score(score: Any) -> float | None:
    if score is None:
        return None
    try:
        numeric = float(score)
    except (TypeError, ValueError) as exc:
        raise ReviewValidationError("ai_score must be a number", path="ai_score") from exc
    if numeric < 0 or numeric > 100:
        raise ReviewValidationError("ai_score must be between 0 and 100", path="ai_score")
    return numeric


def _normalize_status(status: str) -> str:
    value = status.strip().upper()
    if value not in MATCH_STATUSES:
        raise ReviewValidationError("status must be PENDING, APPROVED, or REJECTED", path="status")
    return value


def _normalize_source(source: str) -> str:
    value = source.strip().lower()
    if value not in MATCH_SOURCES:
        raise ReviewValidationError("source must be ai or saved", path="source")
    return value


def _normalize_suggestion(suggestion: str) -> str:
    value = suggestion.strip().lower()
    if value not in SUGGESTIONS:
        raise ReviewValidationError(
            "suggestion must be approve, reject, none, or review",
            path="suggestion",
        )
    return value


def _normalize_decision(decision: str) -> str:
    value = decision.strip().lower()
    if value not in DECISIONS:
        raise ReviewValidationError("decision must be approve or reject", path="decision")
    return value


def _status_for_decision(decision: str) -> str:
    return "APPROVED" if decision == "approve" else "REJECTED"


def _contains_ci(haystack: str | None, needle: str) -> bool:
    if not haystack:
        return False
    return needle.casefold() in haystack.casefold()


def _matches_created_after(match: ReviewMatch, created_after: str) -> bool:
    try:
        created = parse_ts(match.created_at)
        cutoff = parse_ts(created_after)
    except (TypeError, ValueError):
        return True
    return created >= cutoff


class InMemoryReviewStore:
    """Review match + decision + audit store used by tests and Cosmos hydrate."""

    def __init__(self) -> None:
        self._matches: dict[str, ReviewMatch] = {}
        self._decisions: dict[str, DecisionEvent] = {}
        self._audits: dict[str, AuditEvent] = {}

    def _copy_match(self, match: ReviewMatch) -> ReviewMatch:
        return deepcopy(match)

    def _get_owned_match(self, match_id: str, user_id: str) -> ReviewMatch:
        match = self._matches.get(match_id)
        if match is None or match.user_id != user_id:
            raise ReviewNotFoundError("match not found")
        return match

    def _unique_key(self, user_id: str, job_id: str, resume_id: str | None, source: str) -> str:
        return f"{user_id}|{job_id}|{resume_id or ''}|{source}"

    def _assert_unique(
        self,
        user_id: str,
        job_id: str,
        resume_id: str | None,
        source: str,
        *,
        exclude_id: str | None = None,
    ) -> None:
        key = self._unique_key(user_id, job_id, resume_id, source)
        for match in self._matches.values():
            if exclude_id and match.id == exclude_id:
                continue
            if self._unique_key(match.user_id, match.job_id, match.resume_id, match.source) == key:
                raise ReviewConflictError("match already exists for this job, resume, and source")

    def _release_expired_lock(self, match: ReviewMatch) -> None:
        if match.lock_owner and is_lock_expired(match.lock_expires_at):
            previous_owner = match.lock_owner
            match.lock_owner = None
            match.lock_expires_at = None
            match.updated_at = utc_now()
            match.etag = next_etag(match.etag)
            self.record_audit(
                user_id=match.user_id,
                event_type="UNLOCK_EXPIRED",
                match_id=match.id,
                payload={"previous_owner": previous_owner},
            )

    def create_match(
        self,
        user_id: str,
        *,
        job_id: str,
        resume_id: str,
        source: str = "ai",
        job_title: str,
        company: str,
        location: str,
        ai_score: float | None,
        suggestion: str = "none",
        why: str | None = None,
        summary: str | None = None,
        summary_blob_uri: str | None = None,
        highlights_json: list[Any] | None = None,
        match_id: str | None = None,
        queued_at: str | None = None,
    ) -> ReviewMatch:
        owner = _require_str(user_id, field_name="user_id")
        job = _require_str(job_id, field_name="job_id")
        resume = _require_str(resume_id, field_name="resume_id")
        src = _normalize_source(source)
        title = _require_str(job_title, field_name="job_title")
        company_name = _require_str(company, field_name="company")
        loc = _require_str(location, field_name="location")
        score = _validate_score(ai_score)
        sug = _normalize_suggestion(suggestion)
        self._assert_unique(owner, job, resume, src)
        now = utc_now()
        match = ReviewMatch(
            id=match_id or new_id(),
            user_id=owner,
            job_id=job,
            resume_id=resume,
            status="PENDING",
            source=src,
            job_title=title,
            company=company_name,
            location=loc,
            ai_score=score,
            suggestion=sug,
            why=_optional_str(why),
            summary=_optional_str(summary),
            summary_blob_uri=_optional_str(summary_blob_uri),
            highlights_json=highlights_json,
            queued_at=queued_at or now,
            created_at=now,
            updated_at=now,
            etag="1",
        )
        self._matches[match.id] = match
        return self._copy_match(match)

    def update_pending_match(
        self,
        user_id: str,
        match_id: str,
        *,
        ai_score: float | None = None,
        suggestion: str | None = None,
        why: str | None = None,
        summary: str | None = None,
        job_title: str | None = None,
        company: str | None = None,
        location: str | None = None,
    ) -> ReviewMatch:
        match = self._get_owned_match(match_id, user_id)
        if match.status != "PENDING":
            raise ReviewConflictError("match already has a decision")
        if ai_score is not None:
            match.ai_score = _validate_score(ai_score)
        if suggestion is not None:
            match.suggestion = _normalize_suggestion(suggestion)
        if why is not None:
            match.why = _optional_str(why)
        if summary is not None:
            match.summary = _optional_str(summary)
        if job_title:
            match.job_title = _require_str(job_title, field_name="job_title")
        if company:
            match.company = _require_str(company, field_name="company")
        if location:
            match.location = _require_str(location, field_name="location")
        match.updated_at = utc_now()
        match.etag = next_etag(match.etag)
        return self._copy_match(match)

    def get_match(self, match_id: str, *, user_id: str) -> ReviewMatch:
        return self._copy_match(self._get_owned_match(match_id, user_id))

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
    ) -> list[ReviewMatch]:
        rows = [match for match in self._matches.values() if match.user_id == user_id]
        if status:
            wanted = _normalize_status(status)
            rows = [match for match in rows if match.status == wanted]
        if min_score is not None:
            rows = [
                match
                for match in rows
                if match.ai_score is not None and match.ai_score >= float(min_score)
            ]
        if max_score is not None:
            rows = [
                match
                for match in rows
                if match.ai_score is not None and match.ai_score <= float(max_score)
            ]
        if job_title:
            rows = [match for match in rows if _contains_ci(match.job_title, job_title)]
        if company:
            rows = [match for match in rows if _contains_ci(match.company, company)]
        if location:
            rows = [match for match in rows if _contains_ci(match.location, location)]
        if source:
            wanted_source = _normalize_source(source)
            rows = [match for match in rows if match.source == wanted_source]
        if created_after:
            rows = [match for match in rows if _matches_created_after(match, created_after)]
        rows.sort(key=lambda match: match.queued_at, reverse=True)
        return [self._copy_match(match) for match in rows]

    def claim_match(
        self,
        user_id: str,
        match_id: str,
        owner: str,
        *,
        ttl_seconds: int = DEFAULT_LOCK_SECONDS,
        etag: str | None = None,
    ) -> ReviewMatch:
        match = self._get_owned_match(match_id, user_id)
        self._release_expired_lock(match)
        if etag is not None and match.etag != etag:
            raise ReviewPreconditionError("etag mismatch")
        if match.lock_owner and match.lock_owner != owner and not is_lock_expired(match.lock_expires_at):
            raise ReviewConflictError("match is locked by another owner")
        match.lock_owner = _require_str(owner, field_name="owner")
        match.lock_expires_at = lock_until(ttl_seconds)
        match.updated_at = utc_now()
        match.etag = next_etag(match.etag)
        self.record_audit(
            user_id=user_id,
            event_type="LOCK",
            match_id=match.id,
            payload={"ttl_seconds": ttl_seconds},
        )
        return self._copy_match(match)

    def release_lock(self, user_id: str, match_id: str, owner: str) -> ReviewMatch:
        match = self._get_owned_match(match_id, user_id)
        self._release_expired_lock(match)
        if match.lock_owner and match.lock_owner != owner:
            raise ReviewConflictError("lock is held by another owner")
        match.lock_owner = None
        match.lock_expires_at = None
        match.updated_at = utc_now()
        match.etag = next_etag(match.etag)
        return self._copy_match(match)

    def decide(
        self,
        user_id: str,
        match_id: str,
        decision: str,
        *,
        comment: str | None = None,
        overwrite: bool = False,
        etag: str | None = None,
        idempotency_key: str | None = None,
        source: str = "manual",
    ) -> tuple[ReviewMatch, DecisionEvent]:
        match = self._get_owned_match(match_id, user_id)
        if etag is not None and match.etag != etag:
            raise ReviewPreconditionError("etag mismatch")
        action = _normalize_decision(decision)
        if comment is not None and len(comment) > MAX_COMMENT_CHARS:
            raise ReviewValidationError(
                f"comment must be at most {MAX_COMMENT_CHARS} characters",
                path="comment",
            )
        src = source.strip().lower()
        if src not in DECISION_SOURCES:
            raise ReviewValidationError("source must be manual or system", path="source")

        if idempotency_key:
            existing = next(
                (
                    event
                    for event in self._decisions.values()
                    if event.user_id == user_id
                    and event.match_id == match_id
                    and event.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return self._copy_match(match), deepcopy(existing)

        terminal = match.status in {"APPROVED", "REJECTED"}
        if terminal and not overwrite:
            raise ReviewConflictError("match already has a terminal decision")

        supersedes = match.latest_decision_id if terminal and overwrite else None
        prior_versions = [
            event.version
            for event in self._decisions.values()
            if event.match_id == match_id and event.user_id == user_id
        ]
        version = (max(prior_versions) + 1) if prior_versions else 1
        now = utc_now()
        event = DecisionEvent(
            id=new_id(),
            user_id=user_id,
            match_id=match.id,
            decision=action,
            comment=_optional_str(comment),
            source=src,
            version=version,
            supersedes_decision_id=supersedes,
            ai_score=match.ai_score,
            suggestion=match.suggestion,
            decided_at=now,
            created_at=now,
            idempotency_key=_optional_str(idempotency_key),
        )
        self._decisions[event.id] = event
        match.status = _status_for_decision(action)
        match.latest_decision_id = event.id
        match.decided_at = now
        match.updated_at = now
        match.etag = next_etag(match.etag)
        self.record_audit(
            user_id=user_id,
            event_type="DECISION",
            match_id=match.id,
            payload={"decision": action, "overwrite": overwrite, "version": version},
        )
        return self._copy_match(match), deepcopy(event)

    def reopen(self, user_id: str, match_id: str) -> ReviewMatch:
        match = self._get_owned_match(match_id, user_id)
        match.status = "PENDING"
        match.latest_decision_id = None
        match.decided_at = None
        match.updated_at = utc_now()
        match.etag = next_etag(match.etag)
        self.record_audit(
            user_id=user_id,
            event_type="REOPEN",
            match_id=match.id,
            payload={},
        )
        return self._copy_match(match)

    def list_decisions(self, user_id: str, match_id: str | None = None) -> list[DecisionEvent]:
        rows = [event for event in self._decisions.values() if event.user_id == user_id]
        if match_id:
            rows = [event for event in rows if event.match_id == match_id]
        rows.sort(key=lambda event: event.decided_at)
        return [deepcopy(event) for event in rows]

    def record_audit(
        self,
        *,
        user_id: str,
        event_type: str,
        match_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=new_id(),
            user_id=_require_str(user_id, field_name="user_id"),
            match_id=_optional_str(match_id),
            event_type=_require_str(event_type, field_name="event_type"),
            payload=payload or {},
            occurred_at=utc_now(),
        )
        self._audits[event.id] = event
        return deepcopy(event)

    def list_audit(
        self,
        user_id: str,
        *,
        match_id: str | None = None,
        event_type: str | None = None,
    ) -> list[AuditEvent]:
        rows = [event for event in self._audits.values() if event.user_id == user_id]
        if match_id:
            rows = [event for event in rows if event.match_id == match_id]
        if event_type:
            rows = [event for event in rows if event.event_type == event_type]
        rows.sort(key=lambda event: event.occurred_at)
        return [deepcopy(event) for event in rows]
