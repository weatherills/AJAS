"""IMAP/SMTP health scaffolding. Production mail stays on Microsoft Graph."""

from __future__ import annotations

from app.flags import feature_enabled


def imap_health() -> dict[str, object]:
    enabled = feature_enabled("imap_transport")
    return {
        "transport": "graph",
        "imapConfigured": False,
        "smtpConfigured": False,
        "enabled": enabled,
        "status": "disabled" if not enabled else "not_configured",
        "detail": "Gmail/IMAP is out of the Email PRD. Connect Microsoft 365 in Settings.",
    }
