"""In-memory LearningStore — rule engine for the Database PRD."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.learning.constants import (
    DEFAULT_MODEL_VERSION,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    GLOBAL_CONFIG_ID,
)
from app.learning.errors import LearningNotFoundError, LearningValidationError
from app.learning.keys import parse_ts, utc_now
from app.learning.models import (
    DecisionLog,
    MetricsSnapshot,
    ModelParams,
    Recommendation,
    WeightConfig,
    WeightTuningEvent,
)


class InMemoryLearningStore:
    def __init__(self, *, seed: bool = False) -> None:
        self._recs: dict[str, Recommendation] = {}
        self._decisions: dict[str, DecisionLog] = {}
        self._by_rec: dict[tuple[str, str], str] = {}
        self._by_idem: dict[tuple[str, str], str] = {}
        self._params: dict[str, ModelParams] = {}
        self._configs: dict[str, WeightConfig] = {}
        self._events: dict[str, WeightTuningEvent] = {}
        self._metrics: dict[str, MetricsSnapshot] = {}
        self._blobs: dict[str, dict] = {}
        self._seed_global()
        if seed:
            self.seed_demo("local-user")

    def _seed_global(self) -> None:
        now = utc_now()
        if GLOBAL_CONFIG_ID not in self._configs:
            self._configs[GLOBAL_CONFIG_ID] = WeightConfig(
                id=GLOBAL_CONFIG_ID,
                weight_config_id=GLOBAL_CONFIG_ID,
                weights=dict(DEFAULT_WEIGHTS),
                threshold=DEFAULT_THRESHOLD,
                is_active=True,
                created_at=now,
            )

    def upsert_recommendation(self, rec: Recommendation) -> Recommendation:
        existing = self._recs.get(rec.id)
        if existing:
            # Snapshot fields are immutable after create.
            rec.score = existing.score
            rec.score_components = existing.score_components
            rec.weight_config_id = existing.weight_config_id
            rec.threshold = existing.threshold
            rec.generated_at = existing.generated_at
            rec.model_version = existing.model_version
            rec.recommended = existing.recommended
        self._recs[rec.id] = rec
        return deepcopy(self._recs[rec.id])

    def get_recommendation(self, rec_id: str) -> Recommendation:
        row = self._recs.get(rec_id)
        if row is None:
            raise LearningNotFoundError(rec_id)
        return deepcopy(row)

    def list_recommendations(self, user_id: str) -> list[Recommendation]:
        rows = [row for row in self._recs.values() if row.user_id == user_id]
        rows.sort(key=lambda item: item.generated_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def put_decision(self, row: DecisionLog) -> DecisionLog:
        key = (row.user_id, row.recommendation_id)
        prior_id = self._by_rec.get(key)
        if prior_id:
            previous = self._decisions[prior_id]
            row.id = previous.id
            row.created_at = previous.created_at
        self._decisions[row.id] = row
        self._by_rec[key] = row.id
        self._by_idem[(row.user_id, row.idempotency_key)] = row.id
        rec = self._recs.get(row.recommendation_id)
        if rec:
            rec.status = "decided"
        return deepcopy(row)

    def get_decision(self, decision_id: str) -> DecisionLog:
        row = self._decisions.get(decision_id)
        if row is None:
            raise LearningNotFoundError(decision_id)
        return deepcopy(row)

    def get_decision_by_rec(self, user_id: str, recommendation_id: str) -> DecisionLog | None:
        decision_id = self._by_rec.get((user_id, recommendation_id))
        return deepcopy(self._decisions[decision_id]) if decision_id else None

    def get_by_idempotency(self, user_id: str, key: str) -> DecisionLog | None:
        decision_id = self._by_idem.get((user_id, key))
        return deepcopy(self._decisions[decision_id]) if decision_id else None

    def list_decisions(self, user_id: str) -> list[DecisionLog]:
        rows = [row for row in self._decisions.values() if row.user_id == user_id]
        rows.sort(key=lambda item: item.updated_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def get_or_create_params(self, user_id: str) -> ModelParams:
        if not user_id or not user_id.strip():
            raise LearningValidationError("user_id is required", path="user_id")
        existing = self._params.get(user_id)
        if existing:
            return deepcopy(existing)
        now = utc_now()
        row = ModelParams(
            id=user_id,
            user_id=user_id,
            weights=dict(DEFAULT_WEIGHTS),
            score_threshold=DEFAULT_THRESHOLD,
            model_version=DEFAULT_MODEL_VERSION,
            status="active",
            source="global",
            tuning_mode="auto",
            strictness=1,
            sample_size=0,
            effective_at=now,
            updated_at=now,
        )
        self._params[user_id] = row
        return deepcopy(row)

    def put_params(self, row: ModelParams) -> ModelParams:
        # Only one active personalized config conceptually stored on the user row.
        self._params[row.user_id] = row
        return deepcopy(row)

    def put_config(self, row: WeightConfig) -> WeightConfig:
        # At most one globally active default; per-user configs live on ModelParams.
        if row.id == GLOBAL_CONFIG_ID:
            for item in self._configs.values():
                if item.id != row.id:
                    item.is_active = False
        self._configs[row.id] = row
        return deepcopy(row)

    def get_config(self, config_id: str) -> WeightConfig:
        row = self._configs.get(config_id)
        if row is None:
            raise LearningNotFoundError(config_id)
        return deepcopy(row)

    def active_global_config(self) -> WeightConfig:
        for row in self._configs.values():
            if row.is_active:
                return deepcopy(row)
        return deepcopy(self._configs[GLOBAL_CONFIG_ID])

    def put_event(self, row: WeightTuningEvent) -> WeightTuningEvent:
        if not row.tuning_event_id:
            row.tuning_event_id = row.id
        self._events[row.id] = row
        return deepcopy(row)

    def list_events(self, user_id: str | None = None) -> list[WeightTuningEvent]:
        rows = list(self._events.values())
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def put_metrics(self, row: MetricsSnapshot) -> MetricsSnapshot:
        self._metrics[row.id] = row
        return deepcopy(row)

    def list_metrics(self, *, scope_ref: str | None = None) -> list[MetricsSnapshot]:
        rows = list(self._metrics.values())
        if scope_ref:
            rows = [row for row in rows if row.scope_ref == scope_ref]
        rows.sort(key=lambda item: item.period_end, reverse=True)
        return [deepcopy(row) for row in rows]

    def put_blob(self, path: str, payload: dict) -> None:
        self._blobs[path] = dict(payload)

    def seed_demo(self, user_id: str) -> None:
        if any(row.user_id == user_id for row in self._recs.values()):
            return
        now = utc_now()
        params = self.get_or_create_params(user_id)
        jobs = [
            ("job-staff", 0.88, "approve", 6),
            ("job-platform", 0.81, "approve", 18),
            ("job-backend", 0.74, "approve", 30),
            ("job-frontend", 0.62, "reject", 40),
            ("job-analyst", 0.41, "reject", 50),
        ]
        extra = [("job-extra-%s" % idx, 0.55 + (idx % 5) * 0.07, "approve" if idx % 3 else "reject", 8 + idx) for idx in range(17)]
        for job_id, score, decision, hours in [*[(a, b, c, d * 1.0) for a, b, c, d in jobs], *[(a, b, c, float(d)) for a, b, c, d in extra]]:
            rec_id = f"rec-{user_id}-{job_id}"
            generated = hours_ago_safe(hours, now)
            rec = Recommendation(
                id=rec_id,
                user_id=user_id,
                job_id=job_id,
                resume_id="resume-demo",
                score=score,
                score_components={"keyword": score - 0.05, "semantic": score + 0.05},
                weight_config_id=GLOBAL_CONFIG_ID,
                threshold=DEFAULT_THRESHOLD,
                recommended=score >= DEFAULT_THRESHOLD,
                status="decided",
                generated_at=generated,
                expires_at=None,
                model_version=DEFAULT_MODEL_VERSION,
            )
            self.upsert_recommendation(rec)
            self.put_decision(
                DecisionLog(
                    user_id=user_id,
                    recommendation_id=rec_id,
                    job_id=job_id,
                    decision=decision,  # type: ignore[arg-type]
                    score_at_decision=score,
                    threshold_at_decision=DEFAULT_THRESHOLD,
                    model_version=DEFAULT_MODEL_VERSION,
                    idempotency_key=f"seed-{rec_id}",
                    created_at=generated,
                    updated_at=generated,
                )
            )
        params.sample_size = len(self.list_decisions(user_id))
        params.updated_at = now
        self.put_params(params)

    def users_with_decisions(self) -> list[str]:
        return sorted({row.user_id for row in self._decisions.values()})


def hours_ago_safe(hours: float, now: str) -> str:
    stamp = parse_ts(now) - timedelta(hours=hours)
    return stamp.isoformat().replace("+00:00", "Z")
