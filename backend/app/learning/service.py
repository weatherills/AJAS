"""Learning Loop application service."""

from __future__ import annotations

import logging
from datetime import timedelta

from app.config import get_settings as get_app_settings
from app.learning.constants import (
    DEFAULT_MODEL_VERSION,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    GLOBAL_CONFIG_ID,
    MIN_SCORE,
    STRICTNESS_THRESHOLDS,
)
from app.learning.errors import (
    LearningConflictError,
    LearningForbiddenError,
    LearningNotFoundError,
    LearningRateLimitedError,
    LearningStaleError,
    LearningValidationError,
)
from app.learning.keys import as_unit_score, clamp_unit, new_id, parse_ts, utc_now
from app.learning.models import (
    DecisionLog,
    MetricsSnapshot,
    ModelParams,
    Recommendation,
    WeightConfig,
    WeightTuningEvent,
)
from app.learning.queues import JobQueue
from app.learning.store import LearningStore
from app.settings.crypto import seal_token

log = logging.getLogger("ajas")


class LearningService:
    def __init__(self, store: LearningStore, queue: JobQueue, *, local_mode: bool = True, clock=utc_now) -> None:
        self.store = store
        self.queue = queue
        self.local_mode = local_mode
        self.clock = clock
        self._hits: dict[str, list[float]] = {}

    def log_decision(self, user_id: str, body: dict) -> tuple[int, dict]:
        self._rate_limit(user_id)
        rec_id = (body.get("recommendation_id") or body.get("recommendationId") or body.get("matchId") or "").strip()
        job_id = (body.get("job_id") or body.get("jobId") or "").strip()
        decision = (body.get("decision") or "").strip().lower()
        model_version = (body.get("model_version") or body.get("modelVersion") or DEFAULT_MODEL_VERSION).strip()
        key = (body.get("idempotency_key") or body.get("idempotencyKey") or "").strip()
        if not rec_id:
            raise LearningValidationError("recommendation_id is required", path="recommendation_id")
        if not job_id:
            raise LearningValidationError("job_id is required", path="job_id")
        if decision not in {"approve", "reject"}:
            raise LearningValidationError("decision must be approve or reject", path="decision")
        if not key:
            raise LearningValidationError("idempotency_key is required", path="idempotency_key")
        if "score_at_decision" not in body and "scoreAtDecision" not in body and "score" not in body:
            raise LearningValidationError("score_at_decision is required", path="score_at_decision")
        score = as_unit_score(body.get("score_at_decision", body.get("scoreAtDecision", body.get("score"))))
        comment = body.get("comment")
        if comment is not None:
            if not isinstance(comment, str):
                raise LearningValidationError("comment must be a string", path="comment")
            comment = comment.strip()
            if len(comment) > get_app_settings().learning_comment_max:
                raise LearningValidationError("comment exceeds 1000 characters", path="comment")
            if not comment:
                comment = None
        existing = self.store.get_by_idempotency(user_id, key)
        if existing:
            if existing.decision != decision or existing.recommendation_id != rec_id:
                raise LearningConflictError("idempotency key reused with a different decision")
            return 200, {"decision_id": existing.id, "replayed": True}
        rec = self._require_recommendation(user_id, rec_id)
        now = self.clock()
        if rec.expires_at and parse_ts(rec.expires_at) < parse_ts(now):
            rec.status = "expired"
            self.store.upsert_recommendation(rec)
            raise LearningStaleError("recommendation has expired")
        age_days = (parse_ts(now) - parse_ts(rec.generated_at)).days
        if age_days > get_app_settings().learning_stale_days:
            raise LearningStaleError("recommendation has expired")
        sealed = seal_token(comment, get_app_settings().settings_token_key) if comment else None
        row = self.store.put_decision(
            DecisionLog(
                user_id=user_id,
                recommendation_id=rec.id,
                job_id=job_id,
                decision=decision,  # type: ignore[arg-type]
                comment_enc=sealed,
                score_at_decision=score,
                threshold_at_decision=rec.threshold,
                features_snapshot_ref=f"/users/{user_id}/recommendations/{rec.id}.json",
                model_version=model_version,
                idempotency_key=key,
                created_at=now,
                updated_at=now,
            )
        )
        rec.status = "decided"
        self.store.upsert_recommendation(rec)
        self.store.put_blob(
            f"/users/{user_id}/recommendations/{rec.id}.json",
            {"score": rec.score, "components": rec.score_components, "threshold": rec.threshold},
        )
        self.queue.enqueue(
            get_app_settings().learning_decisions_queue,
            {"kind": "decision", "userId": user_id, "decisionId": row.id, "recommendationId": rec.id},
        )
        self._maybe_enqueue_tune(user_id)
        self.drain()
        log.info("ajas.learning.decision user_id=%s rec_id=%s", user_id, rec.id)
        return 201, {"decision_id": row.id}

    def ingest_event(self, payload: dict) -> None:
        """Accept Review's LearningDecisionLogged queue payload."""
        kind = payload.get("eventType") or payload.get("kind")
        if kind == "tune":
            self.tune(payload.get("userId") or payload.get("user_id"), admin=True)
            return
        user_id = payload.get("userId") or payload.get("user_id")
        if not user_id:
            return
        match_id = payload.get("matchId") or payload.get("recommendation_id") or payload.get("recommendationId")
        job_id = payload.get("jobId") or payload.get("job_id") or "unknown"
        outcome = (payload.get("outcome") or payload.get("decision") or "approve").lower()
        if outcome not in {"approve", "reject"}:
            return
        raw_score = payload.get("score")
        if raw_score is None:
            raw_score = payload.get("score_at_decision", 0)
        score = as_unit_score(raw_score if raw_score is not None else 0)
        raw_threshold = payload.get("threshold")
        threshold = as_unit_score(raw_threshold if raw_threshold is not None else DEFAULT_THRESHOLD)
        now = payload.get("occurredAt") or self.clock()
        rec_id = match_id or new_id()
        rec = Recommendation(
            id=rec_id,
            user_id=user_id,
            job_id=job_id,
            resume_id=payload.get("resumeId"),
            score=score,
            score_components={},
            weight_config_id=GLOBAL_CONFIG_ID,
            threshold=threshold,
            recommended=score >= threshold,
            status="pending",
            generated_at=now,
            model_version=payload.get("model_version") or DEFAULT_MODEL_VERSION,
        )
        self.store.upsert_recommendation(rec)
        key = payload.get("decisionId") or payload.get("idempotency_key") or f"review-{rec_id}-{outcome}"
        if self.store.get_by_idempotency(user_id, key):
            return
        self.store.put_decision(
            DecisionLog(
                user_id=user_id,
                recommendation_id=rec_id,
                job_id=job_id,
                decision=outcome,  # type: ignore[arg-type]
                score_at_decision=score,
                threshold_at_decision=threshold,
                model_version=rec.model_version,
                idempotency_key=key,
                created_at=now,
                updated_at=now,
            )
        )
        rec.status = "decided"
        self.store.upsert_recommendation(rec)
        self._maybe_enqueue_tune(user_id)
        self.drain()

    def params(self, user_id: str) -> dict:
        if self.local_mode:
            self.store.seed_demo(user_id)
        row = self.store.get_or_create_params(user_id)
        return {
            "weights": {"keyword": round(row.weights.get("keyword", 0.4), 3), "semantic": round(row.weights.get("semantic", 0.6), 3)},
            "score_threshold": row.score_threshold,
            "model_version": row.model_version,
            "source": row.source,
            "status": row.status,
            "tuningMode": row.tuning_mode,
            "strictness": row.strictness,
            "updated_at": row.updated_at,
            "sample_size": row.sample_size,
        }

    def update_prefs(self, user_id: str, body: dict) -> dict:
        row = self.store.get_or_create_params(user_id)
        mode = (body.get("tuningMode") or body.get("tuning_mode") or row.tuning_mode).lower()
        if mode not in {"auto", "manual"}:
            raise LearningValidationError("tuningMode must be auto or manual", path="tuningMode")
        strictness = body.get("strictness")
        if strictness is not None:
            if strictness not in (0, 1, 2):
                raise LearningValidationError("strictness must be 0, 1, or 2", path="strictness")
        row.tuning_mode = mode  # type: ignore[assignment]
        if mode == "manual" and strictness is not None:
            row.strictness = int(strictness)
            row.score_threshold = STRICTNESS_THRESHOLDS[row.strictness]
            row.source = "personalized"
            row.status = "active"
        if mode == "auto":
            row.source = "global" if row.sample_size < get_app_settings().learning_min_samples else row.source
        row.updated_at = self.clock()
        self.store.put_params(row)
        self._push_matching(row)
        return self.params(user_id)

    def metrics(self, user_id: str, *, scope: str = "self", period: str = "7d", admin: bool = False) -> dict:
        if scope == "global" and not admin:
            raise LearningForbiddenError("admin required for global metrics")
        if period not in {"7d", "30d"}:
            raise LearningValidationError("period must be 7d or 30d", path="period")
        if self.local_mode and scope != "global":
            self.store.seed_demo(user_id)
        target = None if scope == "global" else user_id
        snap = self._compute_metrics(target, period)
        snap.scope_type = "global" if scope == "global" else "user"
        snap.scope_ref = "global" if scope == "global" else user_id
        self.store.put_metrics(snap)
        prior = self._compute_metrics(target, period, offset=True)
        delta = None
        if prior.decisions:
            delta = round((snap.precision_proxy - prior.precision_proxy) * 100, 1)
        return {
            "period": period,
            "scope": scope,
            "approvals": snap.approvals,
            "rejections": snap.rejections,
            "skips": snap.skips,
            "decisions": snap.decisions,
            "suggestions_shown": snap.suggestions_shown,
            "precision_proxy": snap.precision_proxy,
            "recall_proxy": snap.recall_proxy,
            "at_k": {"3": snap.at_3, "10": snap.at_10},
            "threshold": snap.threshold,
            "model_version": snap.model_version,
            "approveRateDeltaPct": delta,
            "liftVsBaseline": round((snap.precision_proxy - 0.5) * 100, 1) if snap.decisions else None,
            "empty": snap.decisions == 0,
            "summary": self._summary_text(snap, period),
        }

    def drift(self, user_id: str, *, period: str = "7d") -> dict:
        body = self.metrics(user_id, period=period)
        baseline = 0.5
        precision = float(body.get("precision_proxy") or 0)
        delta = round(precision - baseline, 4)
        threshold = 0.1
        alert = body.get("decisions", 0) >= 5 and abs(delta) >= threshold
        return {
            "period": period,
            "precision": precision,
            "baseline": baseline,
            "delta": delta,
            "threshold": threshold,
            "alert": alert,
            "liftVsBaseline": body.get("liftVsBaseline"),
        }

    def validate_pipeline(self, events: list) -> dict:
        errors: list[dict] = []
        accepted = 0
        required = {
            "userId": ("userId", "user_id"),
            "matchId": ("matchId", "recommendation_id", "recommendationId"),
            "jobId": ("jobId", "job_id"),
            "decision": ("decision", "outcome"),
            "idempotencyKey": ("idempotencyKey", "idempotency_key"),
        }
        if not isinstance(events, list):
            raise LearningValidationError("events must be a list", path="events")
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                errors.append({"index": index, "error": "object required"})
                continue
            missing = [name for name, keys in required.items() if not any(event.get(key) for key in keys)]
            if missing:
                errors.append({"index": index, "error": f"missing {', '.join(missing)}"})
                continue
            accepted += 1
        return {"accepted": accepted, "rejected": len(errors), "errors": errors}

    def backfill(self, user_id: str, events: list) -> dict:
        check = self.validate_pipeline(events)
        applied = 0
        for event in events:
            if not isinstance(event, dict):
                continue
            payload = {
                "userId": event.get("userId") or event.get("user_id") or user_id,
                "matchId": event.get("matchId") or event.get("recommendation_id"),
                "jobId": event.get("jobId") or event.get("job_id"),
                "outcome": event.get("decision") or event.get("outcome"),
                "score": event.get("score") or event.get("score_at_decision"),
                "decisionId": event.get("idempotencyKey") or event.get("idempotency_key"),
                "eventType": "LearningDecisionLogged",
            }
            if not payload["matchId"] or not payload["jobId"]:
                continue
            self.ingest_event(payload)
            applied += 1
        return {"validated": check, "applied": applied}

    def tune(
        self,
        user_id: str | None,
        *,
        admin: bool,
        window_days: int | None = None,
        min_samples: int | None = None,
        force_activate: bool = False,
        enqueue_only: bool = False,
    ) -> tuple[int, dict]:
        if not admin:
            raise LearningForbiddenError("admin/service only")
        cfg = get_app_settings()
        payload = {
            "kind": "tune",
            "userId": user_id,
            "windowDays": window_days or cfg.learning_window_days,
            "minSamples": min_samples or cfg.learning_min_samples,
            "forceActivate": force_activate,
        }
        self.queue.enqueue(cfg.learning_tune_queue, payload)
        if enqueue_only and not self.local_mode:
            return 202, {"status": "accepted"}
        self.drain()
        return 202, {"status": "accepted", "applied": True}

    def drain(self) -> None:
        cfg = get_app_settings()
        if not hasattr(self.queue, "pop_all"):
            return
        while True:
            events = self.queue.pop_all(cfg.learning_decisions_queue)
            tunes = self.queue.pop_all(cfg.learning_tune_queue)
            if not events and not tunes:
                break
            for item in events:
                if item.get("eventType") == "LearningDecisionLogged":
                    self.ingest_event(item)
            for item in tunes:
                self._run_tune(
                    item.get("userId"),
                    window_days=int(item.get("windowDays") or cfg.learning_window_days),
                    min_samples=int(item.get("minSamples") or cfg.learning_min_samples),
                    force_activate=bool(item.get("forceActivate")),
                )

    def process_decision(self, payload: dict, dequeue_count: int = 1) -> None:
        if payload.get("eventType") == "LearningDecisionLogged" or payload.get("kind") in {None, "decision"}:
            if payload.get("eventType") == "LearningDecisionLogged":
                self.ingest_event(payload)
        if payload.get("kind") == "tune":
            self._run_tune(payload.get("userId"))

    def process_tune(self, payload: dict, dequeue_count: int = 1) -> None:
        self._run_tune(
            payload.get("userId"),
            window_days=int(payload.get("windowDays") or get_app_settings().learning_window_days),
            min_samples=int(payload.get("minSamples") or get_app_settings().learning_min_samples),
            force_activate=bool(payload.get("forceActivate")),
        )

    def poll_all(self) -> None:
        for user_id in self.store.users_with_decisions():
            self._maybe_enqueue_tune(user_id)
        self.drain()

    def active_params(self, user_id: str) -> ModelParams:
        return self.store.get_or_create_params(user_id)

    def _require_recommendation(self, user_id: str, rec_id: str) -> Recommendation:
        try:
            rec = self.store.get_recommendation(rec_id)
        except LearningNotFoundError:
            raise LearningNotFoundError(rec_id) from None
        if rec.user_id != user_id:
            raise LearningNotFoundError(rec_id)
        return rec

    def _maybe_enqueue_tune(self, user_id: str) -> None:
        params = self.store.get_or_create_params(user_id)
        decisions = self.store.list_decisions(user_id)
        params.sample_size = len(decisions)
        self.store.put_params(params)
        if params.tuning_mode != "auto":
            return
        cfg = get_app_settings()
        new_since = [row for row in decisions if row.updated_at >= params.updated_at]
        if len(decisions) >= cfg.learning_min_samples and (
            len(new_since) >= cfg.learning_tune_after or len(decisions) == cfg.learning_min_samples
        ):
            self.queue.enqueue(
                cfg.learning_tune_queue,
                {"kind": "tune", "userId": user_id, "windowDays": cfg.learning_window_days, "minSamples": cfg.learning_min_samples},
            )

    def _run_tune(self, user_id: str | None, *, window_days: int = 30, min_samples: int = 20, force_activate: bool = False) -> None:
        users = [user_id] if user_id else self.store.users_with_decisions()
        for uid in users:
            if not uid:
                continue
            params = self.store.get_or_create_params(uid)
            if params.tuning_mode == "manual" and not force_activate:
                continue
            decisions = self.store.list_decisions(uid)
            cutoff = parse_ts(self.clock()) - timedelta(days=window_days)
            window = [row for row in decisions if parse_ts(row.updated_at) >= cutoff]
            if len(window) < min_samples and not force_activate:
                params.source = "global"
                params.weights = dict(DEFAULT_WEIGHTS)
                params.score_threshold = DEFAULT_THRESHOLD
                params.updated_at = self.clock()
                self.store.put_params(params)
                continue
            approvals = sum(1 for row in window if row.decision == "approve")
            rejections = sum(1 for row in window if row.decision == "reject")
            rate = approvals / max(approvals + rejections, 1)
            old_kw = params.weights.get("keyword", 0.4)
            old_th = params.score_threshold
            cfg = get_app_settings()
            if rate < 0.4:
                new_th = min(0.99, old_th + cfg.learning_max_threshold_delta)
                new_kw = min(0.8, old_kw + min(0.1, cfg.learning_max_weight_delta))
                strictness = 0
            elif rate > 0.75:
                new_th = max(0.10, old_th - cfg.learning_max_threshold_delta)
                new_kw = max(0.2, old_kw - min(0.1, cfg.learning_max_weight_delta))
                strictness = 2
            else:
                new_th = old_th
                new_kw = old_kw
                strictness = 1
            new_kw = max(old_kw - cfg.learning_max_weight_delta, min(old_kw + cfg.learning_max_weight_delta, new_kw))
            new_th = max(old_th - cfg.learning_max_threshold_delta, min(old_th + cfg.learning_max_threshold_delta, new_th))
            new_sem = clamp_unit(1.0 - new_kw)
            current = self._compute_metrics(uid, "7d")
            prior = self._compute_metrics(uid, "7d", offset=True)
            if prior.precision_proxy and current.precision_proxy < prior.precision_proxy * 0.9:
                if params.previous:
                    params.weights = dict(params.previous.get("weights") or DEFAULT_WEIGHTS)
                    params.score_threshold = float(params.previous.get("score_threshold") or DEFAULT_THRESHOLD)
                params.source = "global"
                params.status = "active"
                self.store.put_event(
                    WeightTuningEvent(
                        user_id=uid,
                        old_config_id=params.model_version,
                        new_config_id=params.model_version,
                        reason="precision_proxy dropped >10%",
                        automatic=True,
                        rolled_back=True,
                        created_at=self.clock(),
                    )
                )
                self.store.put_params(params)
                continue
            old_version = params.model_version
            config = WeightConfig(
                id=new_id(),
                weight_config_id=f"weight-{uid[:8]}",
                weights={"keyword": round(new_kw, 3), "semantic": round(new_sem, 3)},
                threshold=round(new_th, 3),
                is_active=True,
                superseded_id=old_version,
                created_at=self.clock(),
            )
            self.store.put_config(config)
            params.previous = {"weights": dict(params.weights), "score_threshold": params.score_threshold}
            params.weights = dict(config.weights)
            params.score_threshold = config.threshold
            params.source = "personalized"
            params.status = "active"
            params.strictness = strictness
            params.sample_size = len(window)
            params.model_version = f"{DEFAULT_MODEL_VERSION}-{config.id[:8]}"
            params.effective_at = self.clock()
            params.updated_at = self.clock()
            self.store.put_params(params)
            self.store.put_event(
                WeightTuningEvent(
                    user_id=uid,
                    old_config_id=old_version,
                    new_config_id=params.model_version,
                    diff={"keyword": round(new_kw - old_kw, 3), "threshold": round(new_th - old_th, 3)},
                    reason="auto-tune",
                    automatic=True,
                    created_at=self.clock(),
                )
            )
            self._push_matching(params)
            log.info("ajas.learning.tune user_id=%s version=%s", uid, params.model_version)

    def _push_matching(self, params: ModelParams) -> None:
        try:
            from app.matching.store import get_matching_store

            store = get_matching_store()
            pct = int(round(params.score_threshold * 100))
            store.update_prefs(params.user_id, threshold_pct=pct)
        except Exception:
            pass

    def _compute_metrics(self, user_id: str | None, period: str, *, offset: bool = False) -> MetricsSnapshot:
        now = parse_ts(self.clock())
        days = 30 if period == "30d" else 7
        end = now - timedelta(days=days if offset else 0)
        start = end - timedelta(days=days)
        recs: list[Recommendation] = []
        decisions: list[DecisionLog] = []
        if user_id:
            recs = self.store.list_recommendations(user_id)
            decisions = self.store.list_decisions(user_id)
        else:
            for uid in self.store.users_with_decisions():
                recs.extend(self.store.list_recommendations(uid))
                decisions.extend(self.store.list_decisions(uid))
        recs_w = [row for row in recs if start <= parse_ts(row.generated_at) < end]
        dec_w = [row for row in decisions if start <= parse_ts(row.updated_at) < end]
        approvals = sum(1 for row in dec_w if row.decision == "approve")
        rejections = sum(1 for row in dec_w if row.decision == "reject")
        skips = sum(1 for row in dec_w if row.decision == "skip")
        shown = [row for row in recs_w if row.recommended]
        scored_min = [row for row in recs_w if row.score >= MIN_SCORE]
        precision = approvals / max(approvals + rejections, 1) if (approvals + rejections) else 0.0
        recall = len(shown) / max(len(scored_min), 1) if scored_min else 0.0
        ranked = sorted(recs_w, key=lambda item: item.score, reverse=True)

        def at_k(k: int) -> float:
            top = ranked[:k]
            if not top:
                return 0.0
            ids = {item.id for item in top}
            hits = sum(1 for row in dec_w if row.recommendation_id in ids and row.decision == "approve")
            return hits / max(len(top), 1)

        params = self.store.get_or_create_params(user_id) if user_id else None
        return MetricsSnapshot(
            scope_ref=user_id or "global",
            scope_type="user" if user_id else "global",
            user_id=user_id,
            period_start=start.isoformat().replace("+00:00", "Z"),
            period_end=end.isoformat().replace("+00:00", "Z"),
            recommendations=len(recs_w),
            decisions=len(dec_w),
            approvals=approvals,
            rejections=rejections,
            skips=skips,
            suggestions_shown=len(shown),
            scored_above_min=len(scored_min),
            precision_proxy=round(precision, 4),
            recall_proxy=round(recall, 4),
            at_3=round(at_k(3), 4),
            at_10=round(at_k(10), 4),
            threshold=(params.score_threshold if params else DEFAULT_THRESHOLD),
            model_version=(params.model_version if params else DEFAULT_MODEL_VERSION),
        )

    def _summary_text(self, snap: MetricsSnapshot, period: str) -> str:
        if snap.decisions == 0:
            return "No learning signals yet. Start by reviewing matches."
        return (
            f"Last {period}: {snap.decisions} decisions, "
            f"{int(round(snap.precision_proxy * 100))}% approve rate, "
            f"{snap.suggestions_shown} matches shown above threshold."
        )

    def _rate_limit(self, user_id: str) -> None:
        import time

        now = time.time()
        window = [stamp for stamp in self._hits.get(user_id, []) if now - stamp < 1]
        if len(window) >= get_app_settings().learning_decision_rate_per_second:
            raise LearningRateLimitedError("too many decisions")
        window.append(now)
        self._hits[user_id] = window
