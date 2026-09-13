"""Retry flaky resume/cover upload endpoints with bounded backoff."""

from __future__ import annotations

from typing import Callable
from app.job_sources.boards import backoff_seconds


def upload_with_retry(send: Callable[[], dict], *, attempts: int = 3) -> dict:
    last: dict = {"ok": False, "error": "not_attempted"}
    for index in range(attempts):
        _ = backoff_seconds(index)
        last = send()
        if last.get("ok"):
            return {**last, "attempts": index + 1}
        if last.get("captcha") or last.get("status") in {401, 403}:
            return {**last, "attempts": index + 1, "ok": False, "action": "needs_manual"}
    return {**last, "attempts": attempts, "ok": False}
