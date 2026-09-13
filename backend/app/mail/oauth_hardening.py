"""OAuth token refresh / scope / error mapping.

Gmail IMAP is out of the Email PRD. This hardens the Graph (Outlook) token
refresh path with the same error classes a Gmail client would need.
"""

from __future__ import annotations

GRAPH_SCOPES = (
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.Send",
    "Mail.ReadWrite",
)


def classify_oauth_error(status: int, body: str = "") -> dict[str, object]:
    hay = (body or "").lower()
    if status == 401 or "invalid_grant" in hay:
        return {"code": "refresh_required", "retry": False, "status": status}
    if status == 403 or "insufficient" in hay or "scope" in hay:
        return {"code": "missing_scope", "retry": False, "status": status}
    if status in {429, 503, 504}:
        return {"code": "transient", "retry": True, "status": status}
    return {"code": "unknown", "retry": status >= 500, "status": status}


def required_scopes() -> tuple[str, ...]:
    return GRAPH_SCOPES
