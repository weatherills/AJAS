"""Flag-gated product integrations (Indeed, LinkedIn, Gmail, Drive, Slack, Harvest).

Live Greenhouse/Lever boards and Microsoft Graph stay the production paths.
These adapters never add extra sources to ``SOURCE_TYPES``.
"""

from app.integrations.service import IntegrationService, get_service, reset_service

__all__ = ["IntegrationService", "get_service", "reset_service"]
