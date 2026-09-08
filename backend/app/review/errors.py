"""Domain errors for the Review & Decision database layer."""


class ReviewStoreError(Exception):
    """Base error for review store operations."""


class ReviewValidationError(ReviewStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class ReviewNotFoundError(ReviewStoreError):
    """A match, decision, or audit row does not exist for this user."""


class ReviewConflictError(ReviewStoreError):
    """Duplicate match, lock held, or conflicting decision."""


class ReviewPreconditionError(ReviewStoreError):
    """ETag / optimistic concurrency check failed."""
