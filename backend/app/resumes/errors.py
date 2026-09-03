"""Domain errors for the Resume Management database layer."""


class ResumeStoreError(Exception):
    """Base error for resume store operations."""


class ResumeValidationError(ResumeStoreError):
    """A document or field failed Database PRD validation."""

    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class ResumeNotFoundError(ResumeStoreError):
    """Resume does not exist in the caller's partition."""


class ResumeSelectionRejectedError(ResumeStoreError):
    """A run cannot select this resume (deleted, not parsed, or cross-user)."""
