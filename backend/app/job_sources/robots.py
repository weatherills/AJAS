"""Consent + robots.txt checks before any optional job-board HTTP."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from app.flags import feature_enabled

from app.job_sources.http_policy import USER_AGENTS, rotate_user_agent

USER_AGENT = USER_AGENTS[0]


def robots_url(target: str) -> str:
    parsed = urlparse(target)
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    return f"{origin}/robots.txt"


def can_fetch(target: str, *, parser: RobotFileParser | None = None, respect: bool | None = None) -> bool:
    """Return False when robots.txt disallows the path. Fail closed if robots cannot be read."""
    if respect is None:
        respect = feature_enabled("respect_robots")
    if not respect:
        return False
    if not feature_enabled("site_policy_consent"):
        return False
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    robots = parser or RobotFileParser()
    try:
        if parser is None:
            robots.set_url(robots_url(target))
            robots.read()
        return bool(robots.can_fetch(rotate_user_agent(seed=target), target))
    except Exception:
        return False
