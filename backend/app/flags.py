"""Feature flags for adapters, automation, and policy gates."""

from __future__ import annotations

from app.config import get_settings

FLAG_DEFAULTS: dict[str, bool] = {
    "indeed_adapter": False,
    "linkedin_adapter": False,
    "glassdoor_adapter": False,
    "wellfound_adapter": False,
    "imap_transport": False,
    "bulk_auto_apply": False,
    "ltr_logging": True,
    "respect_robots": True,
    "site_policy_consent": False,
    "data_retention_purge": True,
}


def feature_flags() -> dict[str, bool]:
    settings = get_settings()
    return {
        "indeed_adapter": bool(settings.flag_indeed_adapter),
        "linkedin_adapter": bool(settings.flag_linkedin_adapter),
        "glassdoor_adapter": bool(settings.flag_glassdoor_adapter),
        "wellfound_adapter": bool(settings.flag_wellfound_adapter),
        "imap_transport": bool(settings.flag_imap_transport),
        "bulk_auto_apply": bool(settings.flag_bulk_auto_apply),
        "ltr_logging": bool(settings.flag_ltr_logging),
        "respect_robots": bool(settings.flag_respect_robots),
        "site_policy_consent": bool(settings.flag_site_policy_consent),
        "data_retention_purge": bool(settings.flag_data_retention_purge),
    }


def feature_enabled(name: str) -> bool:
    flags = feature_flags()
    if name in flags:
        return flags[name]
    return FLAG_DEFAULTS.get(name, False)
