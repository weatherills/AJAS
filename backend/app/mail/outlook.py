"""Outlook / Microsoft Graph as the Email PRD mail transport.

IMAP/SMTP is a flag-gated extra connector (see ``app.integrations.imap``).
"""

from __future__ import annotations

from app.mail.imap_health import imap_health


def outlook_status() -> dict[str, object]:
    imap = imap_health()
    return {
        "provider": "microsoft-graph",
        "imap": False,
        "smtp": False,
        "graph": True,
        "transport": "graph",
        "configured": True,
        "imapConfigured": bool(imap.get("imapConfigured")),
        "imapEnabled": bool(imap.get("enabled")),
        "note": "Email PRD uses Graph. IMAP/SMTP is a separate flag-gated connector.",
    }
