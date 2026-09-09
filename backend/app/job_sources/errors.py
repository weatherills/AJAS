"""Domain errors for the Job Source database layer."""


class JobSourceStoreError(Exception):
    """Base error for job source store operations."""


class JobSourceValidationError(JobSourceStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class JobSourceNotFoundError(JobSourceStoreError):
    """A source, tenant, run, or posting does not exist."""


class JobSourceConflictError(JobSourceStoreError):
    """Uniqueness or optimistic-lock rule failed."""


class JobSourceRateLimitedError(JobSourceStoreError):
    """Token bucket empty or backoff_until is in the future."""
