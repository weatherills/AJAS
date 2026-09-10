"""Per-request IDs for structured logs and response headers."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

import azure.functions as func

_request_id: ContextVar[str | None] = ContextVar("ajas_request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("ajas_user_id", default=None)


def bind_request(req: func.HttpRequest, *, user_id: str | None = None) -> str:
    incoming = (
        req.headers.get("X-Request-Id")
        or req.headers.get("x-request-id")
        or req.headers.get("X-Correlation-Id")
        or ""
    ).strip()
    request_id = incoming or str(uuid4())
    _request_id.set(request_id)
    if user_id:
        _user_id.set(user_id)
    return request_id


def set_user_id(user_id: str | None) -> None:
    _user_id.set(user_id)


def current_request_id() -> str | None:
    return _request_id.get()


def current_user_id() -> str | None:
    return _user_id.get()
