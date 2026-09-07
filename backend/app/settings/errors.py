"""Domain errors for the Settings database layer."""


class SettingsStoreError(Exception):
    """Base error for settings store operations."""


class SettingsValidationError(SettingsStoreError):
    """A document or field failed Database PRD validation."""

    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class SettingsNotFoundError(SettingsStoreError):
    """Settings or connection does not exist in the caller's partition."""


class SettingsConflictError(SettingsStoreError):
    """Optimistic lock failed, or a uniqueness rule was violated."""
