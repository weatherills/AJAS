"""Hot-reload adapter secrets without restarting the process."""

from __future__ import annotations

from app.config import get_settings
from app.secrets import hydrate_from_key_vault

_VERSION = 0
_LISTENERS: list = []


def current_version() -> int:
    return _VERSION


def register(listener) -> None:
    _LISTENERS.append(listener)


def reload_adapters() -> dict[str, object]:
    global _VERSION
    hydrate_from_key_vault()
    get_settings.cache_clear()
    settings = get_settings()
    _VERSION += 1
    for listener in list(_LISTENERS):
        listener(settings)
    return {
        "version": _VERSION,
        "glassdoor": bool(settings.flag_glassdoor_adapter),
        "wellfound": bool(settings.flag_wellfound_adapter),
    }
