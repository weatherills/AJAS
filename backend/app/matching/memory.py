"""In-memory MatchingStore — rule engine for the Database PRD."""

from __future__ import annotations

from copy import deepcopy

from app.matching.constants import (
    DEFAULT_KEYWORD_WEIGHT,
    DEFAULT_MODEL_ID,
    DEFAULT_SAVE_ALL,
    DEFAULT_SEMANTIC_WEIGHT,
    DEFAULT_THRESHOLD_PCT,
    RUN_SOURCES,
    RUN_STATUSES,
)
from app.matching.errors import MatchingConflictError, MatchingNotFoundError, MatchingValidationError
from app.matching.keys import clamp_unit, idempotency_key, is_expired, overall_score_pct, utc_now
from app.matching.models import (
    MatchExplanation,
    MatchRun,
    ModelRegistry,
    UserMatchPrefHistory,
    UserMatchPrefs,
    new_id,
)


class InMemoryMatchingStore:
    def __init__(self, *, seed: bool = True) -> None:
        self._models: dict[str, ModelRegistry] = {}
        self._prefs: dict[str, UserMatchPrefs] = {}
        self._history: dict[str, UserMatchPrefHistory] = {}
        self._runs: dict[str, MatchRun] = {}
        self._explanations: dict[str, MatchExplanation] = {}
        if seed:
            self.seed_default_model()

    def seed_default_model(self) -> ModelRegistry:
        now = utc_now()
        if DEFAULT_MODEL_ID not in self._models:
            self._models[DEFAULT_MODEL_ID] = ModelRegistry(
                id=DEFAULT_MODEL_ID,
                ai_service="azure_openai",
                scorer_model="text-embedding-3-small",
                scorer_model_version="1",
                formula_version="weighted-0.4-0.6",
                keyword_weight=DEFAULT_KEYWORD_WEIGHT,
                semantic_weight=DEFAULT_SEMANTIC_WEIGHT,
                normalization_method="clamp-0-1",
                prompt_version="explain-v1",
                created_at=now,
                updated_at=now,
            )
        return deepcopy(self._models[DEFAULT_MODEL_ID])

    def register_model(self, **kwargs) -> ModelRegistry:
        now = utc_now()
        row = ModelRegistry(
            created_at=kwargs.pop("created_at", now),
            updated_at=now,
            **kwargs,
        )
        if row.keyword_weight < 0 or row.semantic_weight < 0:
            raise MatchingValidationError("weights must be >= 0", path="keyword_weight")
        if abs((row.keyword_weight + row.semantic_weight) - 1.0) > 0.001:
            raise MatchingValidationError("keyword_weight + semantic_weight must equal 1", path="semantic_weight")
        self._models[row.id] = row
        return deepcopy(row)

    def get_model(self, model_id: str) -> ModelRegistry:
        row = self._models.get(model_id)
        if row is None:
            raise MatchingNotFoundError(model_id)
        return deepcopy(row)

    def list_models(self) -> list[ModelRegistry]:
        return [deepcopy(item) for item in self._models.values()]

    def get_or_create_prefs(self, user_id: str) -> UserMatchPrefs:
        if not user_id or not user_id.strip():
            raise MatchingValidationError("user_id is required", path="user_id")
        existing = self._prefs.get(user_id)
        if existing:
            return deepcopy(existing)
        now = utc_now()
        prefs = UserMatchPrefs(
            id=user_id,
            user_id=user_id,
            threshold_pct=DEFAULT_THRESHOLD_PCT,
            save_all_matches=DEFAULT_SAVE_ALL,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._prefs[user_id] = prefs
        return deepcopy(prefs)

    def update_prefs(
        self,
        user_id: str,
        *,
        threshold_pct: int | None = None,
        save_all_matches: bool | None = None,
    ) -> UserMatchPrefs:
        prefs = self.get_or_create_prefs(user_id)
        stored = self._prefs[user_id]
        if threshold_pct is not None:
            if threshold_pct < 0 or threshold_pct > 100:
                raise MatchingValidationError("threshold_pct must be 0–100", path="threshold_pct")
        if (
            threshold_pct is not None
            and threshold_pct == stored.threshold_pct
            and (save_all_matches is None or save_all_matches == stored.save_all_matches)
        ):
            if save_all_matches is None:
                return deepcopy(stored)
        changed = False
        if threshold_pct is not None and threshold_pct != stored.threshold_pct:
            changed = True
        if save_all_matches is not None and save_all_matches != stored.save_all_matches:
            changed = True
        if not changed:
            return deepcopy(stored)
        history = UserMatchPrefHistory(
            user_id=user_id,
            threshold_pct=stored.threshold_pct,
            save_all_matches=stored.save_all_matches,
            version=stored.version,
            created_at=utc_now(),
            detail={"event": "replaced"},
        )
        self._history[history.id] = history
        if threshold_pct is not None:
            stored.threshold_pct = threshold_pct
        if save_all_matches is not None:
            stored.save_all_matches = save_all_matches
        stored.version += 1
        stored.updated_at = utc_now()
        return deepcopy(stored)

    def list_pref_history(self, user_id: str) -> list[UserMatchPrefHistory]:
        rows = [item for item in self._history.values() if item.user_id == user_id]
        rows.sort(key=lambda item: item.created_at)
        return [deepcopy(item) for item in rows]

    def create_run(
        self,
        user_id: str,
        *,
        resume_id: str | None = None,
        resume_hash: str | None = None,
        job_id: str | None = None,
        job_hash: str | None = None,
        model_version_id: str | None = None,
        keyword_raw: float = 0.0,
        keyword_norm: float | None = None,
        semantic_raw: float = 0.0,
        semantic_norm: float | None = None,
        threshold_override: int | None = None,
        explanation_summary: str | None = None,
        explanation_blob_uri: str | None = None,
        feature_vector_blob_uri: str | None = None,
        run_status: str = "completed",
        error_message: str | None = None,
        source: str = "sync",
        idempotency_key_value: str | None = None,
    ) -> MatchRun:
        if not user_id:
            raise MatchingValidationError("user_id is required", path="user_id")
        if not resume_id and not resume_hash:
            raise MatchingValidationError("resume_id or resume_hash is required", path="resume_id")
        if not job_id and not job_hash:
            raise MatchingValidationError("job_id or job_hash is required", path="job_id")
        if run_status not in RUN_STATUSES:
            raise MatchingValidationError(f"invalid run_status {run_status}", path="run_status")
        if source not in RUN_SOURCES:
            raise MatchingValidationError(f"invalid source {source}", path="source")
        model = self.get_model(model_version_id or DEFAULT_MODEL_ID)
        prefs = self.get_or_create_prefs(user_id)
        if threshold_override is not None:
            if threshold_override < 0 or threshold_override > 100:
                raise MatchingValidationError("threshold must be 0–100", path="threshold")
            threshold_used = threshold_override
        else:
            threshold_used = prefs.threshold_pct
        kw_norm = clamp_unit(keyword_norm if keyword_norm is not None else keyword_raw)
        sem_norm = clamp_unit(semantic_norm if semantic_norm is not None else semantic_raw)
        for label, value in (
            ("keyword_raw", keyword_raw),
            ("semantic_raw", semantic_raw),
            ("keyword_norm", kw_norm),
            ("semantic_norm", sem_norm),
        ):
            if value < 0 or value > 1:
                raise MatchingValidationError(f"{label} must be 0.0–1.0", path=label)
        score = overall_score_pct(
            kw_norm,
            sem_norm,
            keyword_weight=model.keyword_weight,
            semantic_weight=model.semantic_weight,
        )
        resume_ref = resume_id or resume_hash or ""
        job_ref = job_id or job_hash or ""
        key = idempotency_key_value or idempotency_key(
            user_id=user_id,
            resume_ref=resume_ref,
            job_ref=job_ref,
            model_version_id=model.id,
            threshold_used=threshold_used,
        )
        for existing in self._runs.values():
            if existing.user_id == user_id and existing.idempotency_key == key:
                raise MatchingConflictError("duplicate match run for idempotency_key")
        now = utc_now()
        is_error = run_status == "error"
        meets = (not is_error) and score >= threshold_used
        saved = False if is_error else (meets or prefs.save_all_matches)
        run = MatchRun(
            user_id=user_id,
            resume_id=resume_id,
            resume_hash=resume_hash,
            job_id=job_id,
            job_hash=job_hash,
            model_version_id=model.id,
            keyword_raw=float(keyword_raw),
            keyword_norm=kw_norm,
            semantic_raw=float(semantic_raw),
            semantic_norm=sem_norm,
            overall_score_pct=0 if is_error else score,
            threshold_used=threshold_used,
            meets_threshold=meets,
            decision_saved=saved,
            explanation_summary=explanation_summary,
            explanation_blob_uri=explanation_blob_uri,
            feature_vector_blob_uri=feature_vector_blob_uri,
            idempotency_key=key,
            run_status=run_status,  # type: ignore[arg-type]
            error_message=error_message,
            source=source,  # type: ignore[arg-type]
            created_at=now,
            completed_at=now if run_status in {"completed", "error"} else None,
            updated_at=now,
        )
        self._runs[run.id] = run
        return deepcopy(run)

    def get_run(self, run_id: str, *, user_id: str | None = None) -> MatchRun:
        run = self._runs.get(run_id)
        if run is None or (user_id and run.user_id != user_id):
            raise MatchingNotFoundError(run_id)
        return deepcopy(run)

    def list_runs(
        self,
        user_id: str,
        *,
        resume_id: str | None = None,
        job_id: str | None = None,
        meets_threshold: bool | None = None,
        saved_only: bool = False,
        include_expired: bool = False,
        now: str | None = None,
    ) -> list[MatchRun]:
        rows = [item for item in self._runs.values() if item.user_id == user_id]
        if resume_id:
            rows = [item for item in rows if item.resume_id == resume_id]
        if job_id:
            rows = [item for item in rows if item.job_id == job_id]
        if meets_threshold is not None:
            rows = [item for item in rows if item.meets_threshold is meets_threshold]
        if saved_only:
            rows = [item for item in rows if item.decision_saved]
        if not include_expired:
            rows = [item for item in rows if not is_expired(item.completed_at, now=now)]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return [deepcopy(item) for item in rows]

    def put_explanation(
        self,
        match_id: str,
        *,
        summary: str,
        highlights: list[str] | None = None,
        gaps: list[str] | None = None,
        explanation_blob_uri: str | None = None,
        user_id: str | None = None,
    ) -> MatchExplanation:
        run = self.get_run(match_id, user_id=user_id)
        for existing in self._explanations.values():
            if existing.match_id == match_id:
                raise MatchingConflictError("explanation already exists for match")
        now = utc_now()
        row = MatchExplanation(
            match_id=run.id,
            summary=summary,
            highlights=list(highlights or []),
            gaps=list(gaps or []),
            explanation_blob_uri=explanation_blob_uri,
            created_at=now,
            updated_at=now,
        )
        self._explanations[row.id] = row
        run_row = self._runs[run.id]
        if not run_row.explanation_summary:
            run_row.explanation_summary = summary[:500]
            run_row.updated_at = now
        return deepcopy(row)

    def get_explanation(self, match_id: str) -> MatchExplanation:
        for item in self._explanations.values():
            if item.match_id == match_id:
                return deepcopy(item)
        raise MatchingNotFoundError(match_id)
