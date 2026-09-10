"""Domain errors for Learning Loop."""


class LearningStoreError(Exception):
    """Base error for learning store operations."""


class LearningValidationError(LearningStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class LearningNotFoundError(LearningStoreError):
    """Recommendation, decision, or params do not exist."""


class LearningConflictError(LearningStoreError):
    """Idempotency key reused with a different payload."""


class LearningForbiddenError(LearningStoreError):
    """Caller lacks admin/service permission."""


class LearningRateLimitedError(LearningStoreError):
    """Decision write rate exceeded."""


class LearningStaleError(LearningStoreError):
    """Recommendation expired and cannot accept a decision."""
