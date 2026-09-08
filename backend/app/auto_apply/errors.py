"""Domain errors for the Auto-Apply database layer."""


class AutoApplyStoreError(Exception):
    """Base error for auto-apply store operations."""


class AutoApplyValidationError(AutoApplyStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class AutoApplyNotFoundError(AutoApplyStoreError):
    """An attempt, package, or related row does not exist for this user."""


class AutoApplyConflictError(AutoApplyStoreError):
    """Duplicate in-flight attempt, locked package, or unique-key clash."""
