"""Roles and permission checks for API + UI guards."""

from __future__ import annotations

from app.auth import DEV_SCOPES, ForbiddenError, Principal
from app.auto_apply.constants import READ_SCOPE as AUTO_APPLY_READ, WRITE_SCOPE as AUTO_APPLY_WRITE
from app.review.constants import READ_SCOPE, WRITE_SCOPE

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLES = (ROLE_USER, ROLE_ADMIN)

USER_SCOPES = frozenset({READ_SCOPE, WRITE_SCOPE, AUTO_APPLY_READ, AUTO_APPLY_WRITE})
ADMIN_SCOPES = USER_SCOPES | frozenset({"admin", "read:ops", "write:ops"})

ROLE_SCOPES = {
    ROLE_USER: USER_SCOPES,
    ROLE_ADMIN: ADMIN_SCOPES,
}


def role_for_principal(principal: Principal) -> str:
    if "admin" in principal.scopes:
        return ROLE_ADMIN
    return ROLE_USER


def require_role(principal: Principal, *allowed: str) -> None:
    role = role_for_principal(principal)
    if role not in allowed:
        raise ForbiddenError(f"Requires role: {' or '.join(allowed)}")


def permissions_payload(principal: Principal) -> dict:
    role = role_for_principal(principal)
    return {
        "userId": principal.user_id,
        "role": role,
        "scopes": sorted(principal.scopes or ROLE_SCOPES[role]),
        "permissions": {
            "review": True,
            "apply": True,
            "settings": True,
            "ops": role == ROLE_ADMIN,
            "learningAdmin": role == ROLE_ADMIN,
        },
    }
