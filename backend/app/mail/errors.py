"""Domain errors for Email Ingestion & Reply."""


class MailStoreError(Exception):
    """Base error for mail store operations."""


class MailValidationError(MailStoreError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class MailNotFoundError(MailStoreError):
    """Thread, message, or mailbox does not exist."""


class MailConflictError(MailStoreError):
    """Idempotency or uniqueness rule failed."""


class MailUnauthorizedError(MailStoreError):
    """Mailbox is not connected or Graph token is invalid."""


class MailForbiddenError(MailStoreError):
    """Caller does not own the mailbox or thread."""


class MailRateLimitedError(MailStoreError):
    """Suggestion or send rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", *, retry_after: int = 86400):
        super().__init__(message)
        self.retry_after = retry_after


class MailUnprocessableError(MailStoreError):
    """Template variables missing or attachment limits exceeded."""
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path
