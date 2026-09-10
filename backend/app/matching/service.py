"""Matching & Ranking application service (Backend PRD)."""

from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from app.config import get_settings as get_app_settings
from app.matching.ab import assign_variant, weights_for
from app.matching.constants import DEFAULT_MODEL_ID
from app.matching.embedder import Embedder, default_embedder
from app.slo import record_latency
from app.matching.errors import (
    MatchingConflictError,
    MatchingNotFoundError,
    MatchingPayloadTooLargeError,
    MatchingRateLimitedError,
    MatchingValidationError,
)
from app.matching.explain import Explainer, default_explainer
from app.matching.keys import idempotency_key, sha256_text, utc_now
from app.matching.models import MatchRun, ModelRegistry
from app.matching.queues import InMemoryJobQueue, JobQueue
from app.matching.scoring import KEYWORD_WEIGHTS_VERSION, cosine_similarity, keyword_score, score_1dp
from app.matching.store import MatchingStore, get_matching_store
from app.matching.texts import NotFoundTextLoader, TextLoader

IDEMPOTENCY_TTL_SEC = 24 * 60 * 60
PRINTABLE_EXTRA = {"\n", "\r", "\t"}
Clock = Callable[[], float]
_EMBED_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="embed")
log = logging.getLogger("ajas")


def _now() -> float:
    return time.time()


def _meta_from_job_text(job_text: str, job_id: str) -> tuple[str, str, str]:
    title = job_id
    company = "Unknown"
    location = "Remote"
    for line in job_text.splitlines():
        lower = line.lower()
        if lower.startswith("title:"):
            title = line.split(":", 1)[1].strip() or title
        elif lower.startswith("company:"):
            company = line.split(":", 1)[1].strip() or company
        elif lower.startswith("location:"):
            location = line.split(":", 1)[1].strip() or location
    return title, company, location


@dataclass
class Operation:
    id: str
    user_id: str
    kind: str
    status: str
    pairs: list[dict[str, Any]]
    results: list[dict[str, Any] | None]
    options: dict[str, Any]
    created_at: str
    error: str | None = None
    cancelled: bool = False
    processed: int = 0
    versions: dict[str, str] = field(default_factory=dict)
    threshold_used: int = 70


class MatchingService:
    def __init__(
        self,
        store: MatchingStore | None = None,
        queue: JobQueue | None = None,
        embedder: Embedder | None = None,
        explainer: Explainer | None = None,
        text_loader: TextLoader | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.store = store or get_matching_store()
        self.queue = queue or InMemoryJobQueue()
        self.embedder = embedder or default_embedder()
        self.explainer = explainer or default_explainer()
        self.text_loader = text_loader or NotFoundTextLoader()
        self.clock = clock or _now
        self.low_confidence_events = 0
        self.semantic_fallback_events = 0
        self._sync_hits: dict[str, list[float]] = {}
        self._idem: dict[tuple[str, str], dict[str, Any]] = {}
        self._operations: dict[str, Operation] = {}
        self._list_cache: dict[tuple, tuple[float, dict]] = {}

    def compute(self, user_id: str, body: dict, *, idempotency_key_header: str | None = None) -> tuple[int, dict]:
        pair = self._single_pair(user_id, body)
        options = self._options(user_id, body, kind="compute")
        fingerprint = self._fingerprint("compute", [pair], options)
        cached = self._cached(user_id, idempotency_key_header, fingerprint)
        if cached:
            return cached
        if options["mode"] == "async":
            status, payload = self._enqueue(user_id, "compute", [pair], options)
        else:
            self._check_rate(user_id)
            result = self._score_pair(user_id, pair, options, source="sync")
            status, payload = 200, result
        self._remember(user_id, idempotency_key_header, fingerprint, status, payload)
        self.invalidate_list_cache(user_id)
        return status, payload

    def rank(self, user_id: str, body: dict, *, idempotency_key_header: str | None = None) -> tuple[int, dict]:
        pairs = self._rank_pairs(user_id, body)
        options = self._options(user_id, body, kind="rank")
        cfg = get_app_settings()
        fingerprint = self._fingerprint("rank", pairs, options)
        cached = self._cached(user_id, idempotency_key_header, fingerprint)
        if cached:
            return cached
        force_async = len(pairs) > cfg.match_rank_async_after or options["mode"] == "async"
        if force_async:
            status, payload = self._enqueue(user_id, "rank", pairs, options)
        else:
            self._check_rate(user_id)
            results = [self._score_pair(user_id, pair, options, source="batch") for pair in pairs]
            status, payload = 200, self._rank_payload(results, options)
        self._remember(user_id, idempotency_key_header, fingerprint, status, payload)
        self.invalidate_list_cache(user_id)
        return status, payload

    def list_matches(
        self,
        user_id: str,
        *,
        job_id: str | None = None,
        resume_id: str | None = None,
        min_score: float | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict:
        if limit < 1 or limit > 100:
            raise MatchingValidationError("limit must be 1–100", path="limit")
        cache_key = (user_id, job_id, resume_id, min_score, limit, cursor)
        hit = self._list_cache.get(cache_key)
        now = self.clock()
        if hit and hit[0] > now:
            body = dict(hit[1])
            body["cache"] = "hit"
            return body
        offset = self._decode_cursor(cursor)
        model = self.store.get_model(DEFAULT_MODEL_ID)
        rows = self.store.list_runs(
            user_id,
            resume_id=resume_id or None,
            job_id=job_id or None,
            saved_only=True,
        )
        items: list[dict] = []
        for run in rows:
            payload = self._run_to_match(run, model)
            if min_score is not None and payload["score"] < min_score:
                continue
            items.append(payload)
        page = items[offset : offset + limit]
        next_cursor = None
        if offset + limit < len(items):
            next_cursor = self._encode_cursor(offset + limit)
        body = {"items": page, "nextCursor": next_cursor, "cache": "miss"}
        self._list_cache[cache_key] = (now + 30, {"items": page, "nextCursor": next_cursor})
        return body

    def get_operation(self, user_id: str, operation_id: str) -> dict:
        op = self._operations.get(operation_id)
        if op is None or op.user_id != user_id:
            raise MatchingNotFoundError(operation_id)
        body: dict[str, Any] = {
            "operationId": op.id,
            "status": op.status,
            "kind": op.kind,
            "thresholdUsed": op.threshold_used,
            "versions": op.versions,
        }
        if op.error:
            body["error"] = op.error
        if op.status == "completed":
            results = [item for item in op.results if item is not None]
            if op.kind == "rank":
                body.update(self._rank_payload(results, op.options))
            elif results:
                body["result"] = results[0]
            persisted = [item for item in results if item.get("persisted")]
            body["summary"] = {
                "pairCount": len(op.pairs),
                "completedCount": len(results),
                "persistedCount": len(persisted),
            }
        return body

    def cancel(self, user_id: str, operation_id: str) -> dict:
        op = self._operations.get(operation_id)
        if op is None or op.user_id != user_id:
            raise MatchingNotFoundError(operation_id)
        if op.status == "queued" and op.processed == 0:
            op.cancelled = True
            op.status = "failed"
            op.error = "cancelled"
            return {"operationId": op.id, "cancelled": True, "status": op.status}
        return {"operationId": op.id, "cancelled": False, "status": op.status}

    def process_compute(self, payload: dict, *, dequeue_count: int = 1) -> None:
        cfg = get_app_settings()
        operation_id = payload["operationId"]
        index = int(payload.get("index", 0))
        op = self._operations.get(operation_id)
        if op is None:
            return
        if op.cancelled:
            return
        if dequeue_count > cfg.match_poison_dequeue:
            self._record_pair_error(op, index, "poisoned after repeated failures")
            return
        op.status = "running"
        pair = op.pairs[index]
        try:
            result = self._score_pair(op.user_id, pair, op.options, source="async" if op.kind == "compute" else "batch")
            op.results[index] = result
        except Exception as exc:
            self._record_pair_error(op, index, str(exc))
            return
        self._finish_pair(op)

    def drain(self) -> None:
        cfg = get_app_settings()
        if not hasattr(self.queue, "pop_all"):
            return
        while True:
            messages = self.queue.pop_all(cfg.match_compute_queue)
            if not messages:
                break
            for payload in messages:
                self.process_compute(payload)

    def _enqueue(self, user_id: str, kind: str, pairs: list[dict], options: dict) -> tuple[int, dict]:
        cfg = get_app_settings()
        model = self.store.get_model(DEFAULT_MODEL_ID)
        op = Operation(
            id=str(uuid4()),
            user_id=user_id,
            kind=kind,
            status="queued",
            pairs=pairs,
            results=[None] * len(pairs),
            options=options,
            created_at=utc_now(),
            versions=self._versions(model),
            threshold_used=options["threshold_used"],
        )
        self._operations[op.id] = op
        for index, _pair in enumerate(pairs):
            self.queue.enqueue(cfg.match_compute_queue, {"operationId": op.id, "index": index})
        return 202, {"operationId": op.id}

    def _record_pair_error(self, op: Operation, index: int, message: str) -> None:
        op.results[index] = {
            "idx": op.pairs[index].get("idx", index),
            "jobId": op.pairs[index].get("job_id"),
            "error": message,
            "persisted": False,
            "score": 0.0,
        }
        if op.error:
            op.error = f"{op.error}; {message}"
        else:
            op.error = message
        self._finish_pair(op)

    def _finish_pair(self, op: Operation) -> None:
        op.processed += 1
        if op.processed < len(op.pairs):
            return
        failures = [item for item in op.results if item is None or item.get("error")]
        successes = [item for item in op.results if item is not None and not item.get("error")]
        if op.cancelled:
            op.status = "failed"
            op.error = op.error or "cancelled"
        elif successes:
            op.status = "completed"
        else:
            op.status = "failed"
            op.error = op.error or "all pairs failed"
        if failures and successes and op.status == "completed":
            op.error = op.error or "partial failure"

    def warmup(self, user_id: str) -> dict:
        started = self.clock()
        sample = "Warmup resume text with python azure kubernetes terraform docker functions."
        error = None
        try:
            self.embedder.embed([sample, sample])
            warm = True
        except Exception as exc:
            warm = False
            error = str(exc)
        elapsed_ms = int((self.clock() - started) * 1000)
        record_latency("POST /v1/matches/warmup", elapsed_ms)
        return {
            "warm": warm,
            "elapsedMs": elapsed_ms,
            "variant": assign_variant(user_id),
            "fallbackRate": self.semantic_fallback_events,
            "error": error,
        }

    def ab_assignment(self, user_id: str) -> dict:
        model = self._model_for_user(user_id)
        keyword, semantic, variant = weights_for(user_id, model.keyword_weight, model.semantic_weight)
        return {
            "variant": variant,
            "weights": {"keyword": keyword, "semantic": semantic},
            "control": {"keyword": model.keyword_weight, "semantic": model.semantic_weight},
        }

    def _score_pair(self, user_id: str, pair: dict, options: dict, *, source: str) -> dict:
        resume_text = pair["resume_text"]
        job_text = pair["job_text"]
        if len(resume_text) < 30 or len(job_text) < 30:
            self.low_confidence_events += 1
        model = self._model_for_user(user_id)
        keyword_w, semantic_w, variant = weights_for(user_id, model.keyword_weight, model.semantic_weight)
        keyword_norm = keyword_score(resume_text, job_text)
        fallback = False
        timeout = get_app_settings().match_semantic_timeout_sec
        try:
            future = _EMBED_POOL.submit(self.embedder.embed, [resume_text, job_text])
            vectors = future.result(timeout=timeout)
            semantic_norm = cosine_similarity(vectors[0], vectors[1]) if len(vectors) >= 2 else 0.0
        except concurrent.futures.TimeoutError:
            semantic_norm = 0.0
            fallback = True
            keyword_w, semantic_w = 1.0, 0.0
            self.semantic_fallback_events += 1
        except Exception:
            semantic_norm = 0.0
        score = score_1dp(keyword_norm, semantic_norm, keyword_w, semantic_w)
        explanation = None
        if options["explanation"]:
            try:
                explanation = self.explainer.explain(
                    resume_text=resume_text,
                    job_text=job_text,
                    keyword=round(keyword_norm * 100.0, 1),
                    semantic=round(semantic_norm * 100.0, 1),
                    score=score,
                )
            except Exception:
                explanation = None
        force_persist = bool(options.get("force_persist"))
        persisted = score >= options["threshold_used"] or force_persist
        match_id = None
        resume_hash = sha256_text(resume_text)
        job_hash = sha256_text(job_text)
        if persisted:
            match_id = self._persist(
                user_id,
                pair,
                model,
                keyword_norm=keyword_norm,
                semantic_norm=semantic_norm,
                threshold_used=options["threshold_used"],
                explanation=explanation,
                source=source,
                resume_hash=resume_hash,
                job_hash=job_hash,
                force_save=force_persist,
            )
            review_pair = dict(pair)
            if force_persist:
                review_pair["save_source"] = "saved"
            self._push_review(user_id, review_pair, score=score, explanation=explanation, match_id=match_id)
        body: dict[str, Any] = {
            "score": score,
            "breakdown": {
                "keyword": round(keyword_norm * 100.0, 1),
                "semantic": round(semantic_norm * 100.0, 1),
                "weights": {"keyword": keyword_w, "semantic": semantic_w},
                "variant": variant,
                "fallback": "keyword_only" if fallback else None,
            },
            "persisted": persisted,
            "thresholdUsed": options["threshold_used"],
            "versions": self._versions(model),
            "input": {"resumeId": pair.get("resume_id"), "jobId": pair.get("job_id")},
            "idx": pair.get("idx"),
        }
        log.info(
            "ajas.match.explain %s",
            json.dumps(
                {
                    "user_id": user_id,
                    "job_id": pair.get("job_id"),
                    "score": score,
                    "breakdown": body["breakdown"],
                    "why": explanation,
                },
                default=str,
            ),
        )
        if pair.get("job_id"):
            body["jobId"] = pair["job_id"]
        if match_id:
            body["matchId"] = match_id
        if explanation is not None:
            body["explanation"] = explanation
        return body

    def _persist(
        self,
        user_id: str,
        pair: dict,
        model: ModelRegistry,
        *,
        keyword_norm: float,
        semantic_norm: float,
        threshold_used: int,
        explanation: str | None,
        source: str,
        resume_hash: str,
        job_hash: str,
        force_save: bool = False,
    ) -> str:
        resume_ref = pair.get("resume_id") or resume_hash
        job_ref = pair.get("job_id") or job_hash
        key = idempotency_key(
            user_id=user_id,
            resume_ref=resume_ref,
            job_ref=job_ref,
            model_version_id=model.id,
            threshold_used=threshold_used,
        )
        existing = self._find_saved(user_id, key)
        if existing:
            return existing.id
        try:
            run = self.store.create_run(
                user_id,
                resume_id=pair.get("resume_id"),
                resume_hash=resume_hash,
                job_id=pair.get("job_id"),
                job_hash=job_hash,
                model_version_id=model.id,
                keyword_raw=keyword_norm,
                keyword_norm=keyword_norm,
                semantic_raw=semantic_norm,
                semantic_norm=semantic_norm,
                threshold_override=threshold_used,
                explanation_summary=explanation,
                run_status="completed",
                source=source,
                idempotency_key_value=key,
                force_save=force_save,
            )
        except MatchingConflictError:
            found = self._find_saved(user_id, key)
            if found:
                return found.id
            raise
        if explanation:
            try:
                self.store.put_explanation(run.id, summary=explanation, user_id=user_id)
            except MatchingConflictError:
                pass
        return run.id

    def _find_saved(self, user_id: str, key: str) -> MatchRun | None:
        for run in self.store.list_runs(user_id, include_expired=True):
            if run.idempotency_key == key:
                return run
        return None

    def _run_to_match(self, run: MatchRun, model: ModelRegistry) -> dict:
        used = self.store.get_model(run.model_version_id)
        score = score_1dp(run.keyword_norm, run.semantic_norm, used.keyword_weight, used.semantic_weight)
        body: dict[str, Any] = {
            "matchId": run.id,
            "score": score,
            "breakdown": {
                "keyword": round(run.keyword_norm * 100.0, 1),
                "semantic": round(run.semantic_norm * 100.0, 1),
                "weights": {"keyword": used.keyword_weight, "semantic": used.semantic_weight},
            },
            "persisted": True,
            "thresholdUsed": run.threshold_used,
            "versions": self._versions(used),
            "input": {"resumeId": run.resume_id, "jobId": run.job_id},
            "createdAt": run.created_at,
            "resumeId": run.resume_id,
            "jobId": run.job_id,
        }
        if run.explanation_summary:
            body["explanation"] = run.explanation_summary
        return body

    def _rank_payload(self, results: list[dict], options: dict) -> dict:
        usable = [item for item in results if item is not None and not item.get("error")]
        usable.sort(key=lambda item: (-float(item.get("score") or 0), item.get("idx") or 0))
        if options.get("filter_below_threshold"):
            usable = [item for item in usable if item.get("score", 0) >= options["threshold_used"]]
        top_n = options.get("top_n")
        applied = usable if not top_n else usable[: max(0, int(top_n))]
        versions = self._versions(self.store.get_model(DEFAULT_MODEL_ID))
        for item in results:
            if item and item.get("versions"):
                versions = item["versions"]
                break
        return {
            "results": applied,
            "topN": top_n if top_n is not None else len(applied),
            "thresholdUsed": options["threshold_used"],
            "versions": versions,
        }

    def _single_pair(self, user_id: str, body: dict) -> dict:
        resume_id, resume_text = self._resolve_text(
            user_id,
            body.get("resumeId"),
            body.get("resumeText"),
            id_path="resumeId",
            text_path="resumeText",
            kind="resume",
        )
        job_id, job_text = self._resolve_text(
            user_id,
            body.get("jobId"),
            body.get("jobText"),
            id_path="jobId",
            text_path="jobText",
            kind="job",
        )
        return {
            "resume_id": resume_id,
            "resume_text": resume_text,
            "job_id": job_id,
            "job_text": job_text,
            "idx": 0,
        }

    def _rank_pairs(self, user_id: str, body: dict) -> list[dict]:
        cfg = get_app_settings()
        resume_id, resume_text = self._resolve_text(
            user_id,
            body.get("resumeId"),
            body.get("resumeText"),
            id_path="resumeId",
            text_path="resumeText",
            kind="resume",
        )
        job_ids = body.get("jobIds") or []
        job_texts = body.get("jobTexts") or []
        if job_ids is None:
            job_ids = []
        if job_texts is None:
            job_texts = []
        if not isinstance(job_ids, list) or not isinstance(job_texts, list):
            raise MatchingValidationError("jobIds and jobTexts must be arrays", path="jobIds")
        if not job_ids and not job_texts:
            raise MatchingValidationError("jobIds or jobTexts is required", path="jobIds")
        if job_ids and job_texts and len(job_ids) != len(job_texts):
            raise MatchingValidationError("jobIds and jobTexts must be the same length", path="jobIds")
        pair_count = len(job_ids) if job_ids else len(job_texts)
        if pair_count > cfg.match_max_rank_pairs:
            raise MatchingValidationError(f"at most {cfg.match_max_rank_pairs} pairs per operation", path="jobIds")
        pairs: list[dict] = []
        if job_ids and job_texts:
            rows: list[tuple[object, object]] = list(zip(job_ids, job_texts, strict=True))
        elif job_ids:
            rows = [(job_id, None) for job_id in job_ids]
        else:
            rows = [(None, text) for text in job_texts]
        for job_id, text in rows:
            if job_id is not None and (not isinstance(job_id, str) or not job_id.strip()):
                raise MatchingValidationError("jobId is invalid", path="jobIds")
            _id, resolved = self._resolve_text(
                user_id, job_id, text, id_path="jobIds", text_path="jobTexts", kind="job"
            )
            pairs.append(
                {
                    "resume_id": resume_id,
                    "resume_text": resume_text,
                    "job_id": _id,
                    "job_text": resolved,
                    "idx": len(pairs),
                }
            )
        return pairs

    def _resolve_text(
        self,
        user_id: str,
        item_id: Any,
        text: Any,
        *,
        id_path: str,
        text_path: str,
        kind: str,
    ) -> tuple[str | None, str]:
        if text is not None and text != "":
            return (str(item_id) if isinstance(item_id, str) and item_id.strip() else None, self._validate_text(text, text_path))
        if isinstance(item_id, str) and item_id.strip():
            loaded = (
                self.text_loader.load_resume(user_id, item_id)
                if kind == "resume"
                else self.text_loader.load_job(user_id, item_id)
            )
            return item_id.strip(), self._validate_text(loaded, id_path)
        raise MatchingValidationError(f"{id_path} or {text_path} is required", path=text_path)

    def _validate_text(self, value: Any, path: str) -> str:
        cfg = get_app_settings()
        if not isinstance(value, str):
            raise MatchingValidationError("empty or non-text input", path=path)
        if "\x00" in value:
            raise MatchingValidationError("empty or non-text input", path=path)
        if not value.strip():
            raise MatchingValidationError("empty or non-text input", path=path)
        if len(value) > cfg.match_max_text_chars:
            raise MatchingPayloadTooLargeError("payload exceeds 100k characters")
        printable = sum(1 for ch in value if ch.isprintable() or ch in PRINTABLE_EXTRA)
        if printable / max(len(value), 1) < 0.7:
            raise MatchingValidationError("empty or non-text input", path=path)
        return value

    def _options(self, user_id: str, body: dict, *, kind: str) -> dict:
        prefs = self.store.get_or_create_prefs(user_id)
        raw_threshold = body.get("threshold")
        if raw_threshold is None:
            threshold_used = prefs.threshold_pct
            overlay = self._learning_params(user_id)
            if overlay is not None and overlay.source == "personalized":
                threshold_used = int(round(overlay.score_threshold * 100))
        else:
            if isinstance(raw_threshold, bool) or not isinstance(raw_threshold, (int, float)):
                raise MatchingValidationError("threshold must be 0–100", path="threshold")
            if raw_threshold < 0 or raw_threshold > 100:
                raise MatchingValidationError("threshold must be 0–100", path="threshold")
            threshold_used = int(round(float(raw_threshold)))
        mode = body.get("mode") or "sync"
        if mode not in {"sync", "async"}:
            raise MatchingValidationError("mode must be sync or async", path="mode")
        explanation = bool(body.get("explanation"))
        top_n = body.get("topN")
        if top_n is not None:
            if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
                raise MatchingValidationError("topN must be a positive integer", path="topN")
        filter_below = bool(body.get("filterBelowThreshold"))
        force_persist = bool(body.get("persist") or body.get("saveMatch"))
        return {
            "kind": kind,
            "threshold_used": threshold_used,
            "mode": mode,
            "explanation": explanation,
            "top_n": top_n,
            "filter_below_threshold": filter_below,
            "force_persist": force_persist,
        }

    def _push_review(self, user_id: str, pair: dict, *, score: float, explanation: str | None, match_id: str | None) -> None:
        job_id = pair.get("job_id")
        resume_id = pair.get("resume_id")
        if not job_id or not resume_id:
            return
        title, company, location = _meta_from_job_text(pair.get("job_text") or "", job_id)
        try:
            from app.job_sources.runtime import try_get_service as try_jobs

            jobs = try_jobs()
            if jobs is not None:
                card = jobs.get_feed_job(job_id)
                title = card.get("title") or title
                company = card.get("company") or company
                location = card.get("location") or location
        except Exception:
            pass
        try:
            from app.review.runtime import get_service as get_review_service

            get_review_service().upsert_scored_match(
                user_id,
                job_id=job_id,
                resume_id=resume_id,
                job_title=title,
                company=company,
                location=location,
                score=score,
                why=explanation,
                source="saved" if pair.get("save_source") == "saved" else "ai",
                match_id=match_id,
            )
        except Exception:
            pass

    def _learning_params(self, user_id: str):
        try:
            from app.learning.runtime import try_get_service

            service = try_get_service()
            if service is None:
                return None
            return service.active_params(user_id)
        except Exception:
            return None

    def _model_for_user(self, user_id: str):
        model = self.store.get_model(DEFAULT_MODEL_ID)
        params = self._learning_params(user_id)
        if params is None or params.source != "personalized":
            return model
        return model.model_copy(
            update={
                "keyword_weight": params.weights.get("keyword", model.keyword_weight),
                "semantic_weight": params.weights.get("semantic", model.semantic_weight),
            }
        )

    def _check_rate(self, user_id: str) -> None:
        cfg = get_app_settings()
        now = self.clock()
        window = [stamp for stamp in self._sync_hits.get(user_id, []) if now - stamp < 60]
        if len(window) >= cfg.match_sync_rate_per_minute:
            raise MatchingRateLimitedError("sync rate limit exceeded")
        window.append(now)
        self._sync_hits[user_id] = window

    def _fingerprint(self, kind: str, pairs: list[dict], options: dict) -> str:
        payload = {
            "kind": kind,
            "pairs": [
                {
                    "resume": sha256_text(item["resume_text"]),
                    "job": sha256_text(item["job_text"]),
                    "resumeId": item.get("resume_id"),
                    "jobId": item.get("job_id"),
                }
                for item in pairs
            ],
            "options": {
                "threshold": options["threshold_used"],
                "explanation": options["explanation"],
                "mode": options["mode"],
                "topN": options.get("top_n"),
                "filterBelowThreshold": options.get("filter_below_threshold"),
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def invalidate_list_cache(self, user_id: str) -> None:
        self._list_cache = {key: value for key, value in self._list_cache.items() if key[0] != user_id}

    def _cached(self, user_id: str, header: str | None, fingerprint: str) -> tuple[int, dict] | None:
        if not header:
            return None
        key = (user_id, header.strip())
        row = self._idem.get(key)
        if not row:
            return None
        if self.clock() - row["created"] > IDEMPOTENCY_TTL_SEC:
            self._idem.pop(key, None)
            return None
        if row["fingerprint"] != fingerprint:
            raise MatchingConflictError("Idempotency-Key reused with different inputs")
        return row["status"], dict(row["body"])

    def _remember(self, user_id: str, header: str | None, fingerprint: str, status: int, body: dict) -> None:
        if not header:
            return
        self._idem[(user_id, header.strip())] = {
            "created": self.clock(),
            "fingerprint": fingerprint,
            "status": status,
            "body": dict(body),
        }

    def _versions(self, model: ModelRegistry) -> dict[str, str]:
        return {
            "algorithm": model.formula_version,
            "embeddingsModel": model.scorer_model,
            "prompt": model.prompt_version,
            "keywordWeights": KEYWORD_WEIGHTS_VERSION,
            "normalization": model.normalization_method,
        }

    def _encode_cursor(self, offset: int) -> str:
        raw = json.dumps({"o": offset}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    def _decode_cursor(self, cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
            offset = int(payload["o"])
        except (ValueError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
            raise MatchingValidationError("invalid cursor", path="cursor") from exc
        if offset < 0:
            raise MatchingValidationError("invalid cursor", path="cursor")
        return offset
