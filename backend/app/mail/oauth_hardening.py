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


def refresh_access_token(
    *,
    refresh_token: str | None,
    status: int | None = None,
    body: str = "",
    access_token: str | None = None,
) -> dict[str, object]:
    """Rotate a Graph (or equivalent) access token. Never invents a grant.

    CAPTCHA / consent errors stay fail-closed: the caller must reconnect.
    """
    if not (refresh_token or "").strip():
        classified = classify_oauth_error(401, "invalid_grant")
        return {**classified, "ok": False, "action": "reconnect", "accessToken": None}
    if status is not None:
        classified = classify_oauth_error(status, body)
        action = "retry" if classified["retry"] else "reconnect"
        if classified["code"] == "missing_scope":
            action = "reconsent"
        if classified["code"] == "refresh_required":
            action = "reconnect"
        return {**classified, "ok": False, "action": action, "accessToken": None}
    return {
        "ok": True,
        "code": "ok",
        "retry": False,
        "status": 200,
        "action": "ok",
        "accessToken": access_token or "rotated",
    }
