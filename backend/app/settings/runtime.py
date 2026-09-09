"""Process-wide SettingsService used by HTTP triggers."""

from __future__ import annotations

from app.settings.service import SettingsService

_service: SettingsService | None = None


def get_service() -> SettingsService:
    global _service
    if _service is None:
        from app.settings.queues import default_queue
        from app.settings.store import get_settings_store

        _service = SettingsService(store=get_settings_store(), queue=default_queue())
    return _service


def set_service(service: SettingsService | None) -> None:
    global _service
    _service = service
