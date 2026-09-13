"""Scoped automation tokens (ingest, match, apply)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

SCOPES = ("ingest", "match", "apply", "ops")


@dataclass
class AutomationToken:
    token: str
    scopes: tuple[str, ...]
    user_id: str


_TOKENS: dict[str, AutomationToken] = {}


def issue(user_id: str, scopes: list[str]) -> AutomationToken:
    allowed = tuple(scope for scope in scopes if scope in SCOPES)
    token = AutomationToken(token=secrets.token_urlsafe(16), scopes=allowed, user_id=user_id)
    _TOKENS[token.token] = token
    return token


def authorize(token: str, scope: str) -> bool:
    row = _TOKENS.get(token)
    if not row:
        return False
    return scope in row.scopes
