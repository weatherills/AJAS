"""Outlook / Microsoft Graph as the mail transport (IMAP/SMTP stay stubs)."""

from __future__ import annotations

from app.mail.imap_health import imap_health


def outlook_status() -> dict[str, object]:
    imap = imap_health()
    return {
        "provider": "microsoft-graph",
        "imap": False,
        "smtp": False,
        "graph": True,
        "transport": imap.get("transport") or "graph",
        "configured": bool(imap.get("transport") == "graph"),
        "imapConfigured": bool(imap.get("imapConfigured")),
        "note": "Email PRD uses Graph only; IMAP/SMTP are not implemented.",
    }
