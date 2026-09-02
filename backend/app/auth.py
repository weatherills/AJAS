"""Authentication seam.

The PRDs require Azure AD / B2C bearer-token auth with per-user ownership
enforcement on every feature endpoint. This module defines the stable interface
that handlers depend on; real token validation is implemented in a feature
phase (see the security sections of the backend PRDs).
"""
from dataclasses import dataclass

import azure.functions as func


class AuthError(Exception):
    """Raised when a request is unauthenticated or unauthorized."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Extended as auth is implemented."""

    user_id: str


def get_principal(req: func.HttpRequest) -> Principal:
    """Resolve the authenticated principal from a request.

    Placeholder: JWT validation against Azure AD / B2C is wired up in a feature
    phase. Kept unimplemented so no endpoint accidentally trusts unverified
    input during skeleton development.
    """
    raise NotImplementedError(
        "JWT validation is implemented during a feature phase; see backend PRDs."
    )
