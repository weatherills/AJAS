"""Kanban match_records / match_evidence plane: IDs, ETag upserts, TTL, prune."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

from app.matching.constants import (
    DEFAULT_MODEL_ID,
    DEFAULT_PRUNE_KEEP,
    EVIDENCE_CONTAINER,
    EVIDENCE_TTL_SECONDS,
    RECORDS_CONTAINER,
    SCHEMA_VERSION,
)
from app.matching.errors import MatchingConflictError, MatchingNotFoundError, MatchingValidationError
from app.matching.keys import utc_now
from app.storage.dal import ConflictError, CosmosDAL

log = logging.getLogger("ajas")


def prune_keep() -> int:
    raw = os.environ.get("MATCH_PRUNE_KEEP")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            return DEFAULT_PRUNE_KEEP
    try:
        from app.config import get_settings

        return max(1, int(getattr(get_settings(), "match_prune_keep", DEFAULT_PRUNE_KEEP)))
    except Exception:
        return DEFAULT_PRUNE_KEEP


def match_record_id(*, user_id: str, job_id: str, resume_id: str, model_version: str) -> str:
    """Deterministic current-record id: hash(userId, jobId, resumeId, modelVersion)."""
    payload = f"{user_id}|{job_id}|{resume_id}|{model_version or DEFAULT_MODEL_ID}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def version_id(family: str, created_at: str, salt: str = "") -> str:
    digest = hashlib.sha1(f"{family}|{created_at}|{salt}".encode("utf-8")).hexdigest()[:12]
    return f"{family}:{digest}"


def family_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("jobId") or row.get("job_id") or ""),
        str(row.get("resumeId") or row.get("resume_id") or ""),
        str(row.get("modelVersion") or row.get("model_version") or DEFAULT_MODEL_ID),
    )


def _created_at(row: dict[str, Any]) -> str:
    return str(row.get("createdAt") or row.get("created_at") or "")


def select_keep(rows: list[dict[str, Any]], *, keep: int | None = None) -> dict[str, Any]:
    """Keep latest N per (jobId, resumeId, modelVersion). Ties break by createdAt then id."""
    n = int(keep if keep is not None else prune_keep())
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(family_key(row), []).append(row)
    retain: list[dict[str, Any]] = []
    drop: list[dict[str, Any]] = []
    for members in groups.values():
        ordered = sorted(
            members,
            key=lambda item: (_created_at(item), str(item.get("id") or "")),
            reverse=True,
        )
        retain.extend(ordered[:n])
        drop.extend(ordered[n:])
    return {"keep": n, "retain": retain, "delete": drop, "groups": len(groups)}


def _next_etag(previous: str | None) -> str:
    if not previous:
        return "1"
    try:
        return str(int(previous) + 1)
    except ValueError:
        return "1"


class MatchRecordStore:
    """In-memory / DAL-backed store used by HTTP, prune jobs, and tests."""

    def __init__(self, dal: CosmosDAL | None = None) -> None:
        self._dal = dal
        self._records: dict[tuple[str, str], dict[str, Any]] = {}
        self._evidence: dict[tuple[str, str], dict[str, Any]] = {}
        self.telemetry: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._records.clear()
        self._evidence.clear()
        self.telemetry.clear()

    def _emit(self, event: str, **payload: Any) -> dict[str, Any]:
        row = {"event": event, "at": utc_now(), "source": "matching", **payload}
        self.telemetry.append(row)
        log.info("ajas.matching %s", event)
        return row

    def _get_record(self, user_id: str, item_id: str) -> dict[str, Any] | None:
        if self._dal:
            try:
                return self._dal.read(RECORDS_CONTAINER, item_id, partition_key=user_id)
            except KeyError:
                return None
        return self._records.get((user_id, item_id))

    def _put_record(self, row: dict[str, Any], *, etag: str | None = None, create_only: bool = False) -> dict[str, Any]:
        user_id = str(row["userId"])
        item_id = str(row["id"])
        if self._dal:
            if create_only:
                return self._dal.create(RECORDS_CONTAINER, row)
            if etag:
                return self._dal.replace(RECORDS_CONTAINER, item_id, row, etag=etag)
            return self._dal.upsert(RECORDS_CONTAINER, row)
        key = (user_id, item_id)
        existing = self._records.get(key)
        if create_only and existing:
            raise MatchingConflictError("match record exists")
        if existing and etag and existing.get("_etag") != etag:
            raise ConflictError("etag mismatch")
        stored = dict(row)
        stored["_etag"] = _next_etag(existing.get("_etag") if existing else None)
        self._records[key] = stored
        return dict(stored)

    def _delete_record(self, user_id: str, item_id: str) -> None:
        if self._dal:
            self._dal.delete(RECORDS_CONTAINER, item_id, partition_key=user_id)
            return
        self._records.pop((user_id, item_id), None)

    def upsert_score(
        self,
        *,
        user_id: str,
        job_id: str,
        resume_id: str,
        model_version: str = DEFAULT_MODEL_ID,
        score: float,
        evidence: list[str] | None = None,
        created_at: str | None = None,
        etag: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not job_id or not resume_id:
            raise MatchingValidationError("jobId and resumeId required")
        started = time.perf_counter()
        family = match_record_id(
            user_id=user_id, job_id=job_id, resume_id=resume_id, model_version=model_version
        )
        stamp = created_at or utc_now()
        current = {
            "id": family,
            "userId": user_id,
            "user_id": user_id,
            "jobId": job_id,
            "resumeId": resume_id,
            "modelVersion": model_version,
            "score": float(score),
            "createdAt": stamp,
            "updatedAt": utc_now(),
            "schemaVersion": SCHEMA_VERSION,
            "latest": True,
            "familyId": family,
            **(extra or {}),
        }
        existing = self._get_record(user_id, family)
        try:
            if existing is None:
                saved = self._put_record(current, create_only=True)
                status = "created"
            else:
                current["createdAt"] = existing.get("createdAt") or stamp
                saved = self._put_record(current, etag=etag or existing.get("_etag"))
                status = "updated"
        except (MatchingConflictError, ConflictError):
            self._emit("score_conflict", correlationId=family, status="conflict", errorCode="ETAG")
            raise
        version = dict(current)
        version["id"] = version_id(family, stamp, salt=f"{score}|{time.time_ns()}")
        version["latest"] = False
        version["parentId"] = family
        self._put_record(version)
        evidence_row = None
        if evidence:
            evidence_row = self.put_evidence(user_id=user_id, match_id=family, sentences=evidence, created_at=stamp)
        self._emit(
            "score",
            correlationId=family,
            status=status,
            latencyMs=int((time.perf_counter() - started) * 1000),
            errorCode=None,
            jobId=job_id,
            resumeId=resume_id,
        )
        return {"record": saved, "versionId": version["id"], "evidence": evidence_row, "status": status}

    def put_evidence(
        self,
        *,
        user_id: str,
        match_id: str,
        sentences: list[str],
        created_at: str | None = None,
    ) -> dict[str, Any]:
        stamp = created_at or utc_now()
        item_id = version_id(match_id, stamp, salt="evidence")
        row = {
            "id": item_id,
            "userId": user_id,
            "user_id": user_id,
            "matchId": match_id,
            "sentences": list(sentences),
            "createdAt": stamp,
            "schemaVersion": SCHEMA_VERSION,
            "ttl": EVIDENCE_TTL_SECONDS,
        }
        if self._dal:
            return self._dal.upsert(EVIDENCE_CONTAINER, row)
        row["_etag"] = "1"
        self._evidence[(user_id, item_id)] = row
        return dict(row)

    def get(self, user_id: str, item_id: str) -> dict[str, Any]:
        row = self._get_record(user_id, item_id)
        if not row:
            raise MatchingNotFoundError("match record not found")
        return row

    def list_records(
        self,
        user_id: str,
        *,
        job_id: str | None = None,
        resume_id: str | None = None,
        latest_only: bool = True,
    ) -> list[dict[str, Any]]:
        if self._dal:
            page = self._dal.query(RECORDS_CONTAINER, "SELECT * FROM c", partition_key=user_id, max_items=100)
            rows = list(page.items)
        else:
            rows = [dict(row) for (uid, _), row in self._records.items() if uid == user_id]
        out = []
        for row in rows:
            if latest_only and not row.get("latest"):
                continue
            if job_id and str(row.get("jobId")) != job_id:
                continue
            if resume_id and str(row.get("resumeId")) != resume_id:
                continue
            out.append(row)
        out.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return out

    def list_evidence(self, user_id: str, match_id: str) -> list[dict[str, Any]]:
        if self._dal:
            page = self._dal.query(EVIDENCE_CONTAINER, "SELECT * FROM c", partition_key=user_id, max_items=100)
            rows = [row for row in page.items if str(row.get("matchId")) == match_id]
        else:
            rows = [dict(row) for (uid, _), row in self._evidence.items() if uid == user_id and row.get("matchId") == match_id]
        rows.sort(key=_created_at)
        return rows

    def prune(self, user_id: str, *, keep: int | None = None, dry_run: bool = False) -> dict[str, Any]:
        if self._dal:
            page = self._dal.query(RECORDS_CONTAINER, "SELECT * FROM c", partition_key=user_id, max_items=200)
            rows = list(page.items)
        else:
            rows = [dict(row) for (uid, _), row in self._records.items() if uid == user_id]
        versions = [row for row in rows if not row.get("latest")]
        plan = select_keep(versions, keep=keep)
        deleted_ids = [str(row.get("id")) for row in plan["delete"]]
        if not dry_run:
            for row in plan["delete"]:
                self._delete_record(user_id, str(row["id"]))
        result = {
            "userId": user_id,
            "dryRun": dry_run,
            "keep": plan["keep"],
            "scanned": len(versions),
            "retained": len(plan["retain"]),
            "deleted": 0 if dry_run else len(deleted_ids),
            "wouldDelete": deleted_ids if dry_run else [],
            "deletedIds": [] if dry_run else deleted_ids,
        }
        self._emit("prune", correlationId=user_id, status="ok", dryRun=dry_run, deleted=result["deleted"], scanned=result["scanned"])
        log.info(
            "ajas.matching.prune user=%s dry_run=%s scanned=%s deleted=%s keep=%s",
            user_id,
            dry_run,
            result["scanned"],
            result["deleted"] or len(deleted_ids),
            plan["keep"],
        )
        return result

    def batch_rescore(self, user_id: str, pairs: list[dict[str, Any]], *, model_version: str = DEFAULT_MODEL_ID) -> dict[str, Any]:
        results = []
        for pair in pairs:
            score = float(pair.get("score") or 0)
            saved = self.upsert_score(
                user_id=user_id,
                job_id=str(pair.get("jobId") or pair.get("job_id") or ""),
                resume_id=str(pair.get("resumeId") or pair.get("resume_id") or ""),
                model_version=str(pair.get("modelVersion") or model_version),
                score=score,
                evidence=list(pair.get("evidence") or []),
            )
            results.append(saved["record"])
            self._emit("rescore", correlationId=saved["record"]["id"], status="ok", latencyMs=0)
        return {"count": len(results), "items": results}


_STORE: MatchRecordStore | None = None


def get_record_store() -> MatchRecordStore:
    global _STORE
    if _STORE is None:
        _STORE = MatchRecordStore()
    return _STORE


def reset_record_store() -> None:
    global _STORE
    if _STORE is not None:
        _STORE.reset()
    _STORE = MatchRecordStore()
