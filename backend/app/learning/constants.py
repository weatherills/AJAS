"""Learning Loop database constants (Database PRD)."""

from typing import Final, Literal

DecisionValue = Literal["approve", "reject", "skip"]
ParamStatus = Literal["active", "staged"]
ParamSource = Literal["global", "personalized"]
TuningMode = Literal["auto", "manual"]
RecommendationStatus = Literal["pending", "decided", "expired"]

DECISION_VALUES: Final[frozenset[str]] = frozenset({"approve", "reject", "skip"})
DEFAULT_WEIGHTS: Final[dict[str, float]] = {"keyword": 0.4, "semantic": 0.6}
DEFAULT_THRESHOLD: Final[float] = 0.70
DEFAULT_MODEL_VERSION: Final[str] = "learning-v1"
GLOBAL_CONFIG_ID: Final[str] = "weight-global-v1"
MIN_SCORE: Final[float] = 0.2
STRICTNESS_THRESHOLDS: Final[dict[int, float]] = {0: 0.80, 1: 0.70, 2: 0.60}

RECS_CONTAINER: Final[str] = "recommendations"
DECISIONS_CONTAINER: Final[str] = "decision_log"
PARAMS_CONTAINER: Final[str] = "model_params"
CONFIGS_CONTAINER: Final[str] = "weight_config"
EVENTS_CONTAINER: Final[str] = "weight_tuning_event"
METRICS_CONTAINER: Final[str] = "metrics_snapshot"

USER_PK: Final[str] = "/user_id"
SCOPE_PK: Final[str] = "/scope_ref"
CONFIG_PK: Final[str] = "/weight_config_id"
EVENT_PK: Final[str] = "/tuning_event_id"
