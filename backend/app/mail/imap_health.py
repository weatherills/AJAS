"""IMAP/SMTP health. Graph stays the Email PRD transport."""

from __future__ import annotations

from app.flags import feature_enabled


def imap_health() -> dict[str, object]:
    from app.integrations.imap import credentials_present, live_fetch_allowed, smtp_configured

    enabled = feature_enabled("imap_transport")
    configured = credentials_present()
    if not enabled:
        status = "flag_off"
    elif configured:
        status = "ok"
    else:
        status = "not_configured"
    return {
        "transport": "graph",
        "connector": "imap",
        "imapConfigured": configured,
        "smtpConfigured": smtp_configured(),
        "enabled": enabled,
        "liveFetch": live_fetch_allowed(),
        "status": status,
        "detail": (
            "Graph is the Email PRD mailbox. IMAP/SMTP is a flag-gated extra connector "
            "(fixture ingest unless IMAP_LIVE + SSL + allowlisted host)."
        ),
    }
