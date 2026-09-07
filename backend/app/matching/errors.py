"""Domain errors for the Matching database layer."""


class MatchingStoreError(Exception):
    """Base error for matching store operations."""


class MatchingValidationError(MatchingStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class MatchingNotFoundError(MatchingStoreError):
    """A run, preference, explanation, or model does not exist."""


class MatchingConflictError(MatchingStoreError):
    """Idempotency or uniqueness rule failed."""
