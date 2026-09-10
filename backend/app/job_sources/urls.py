"""HTTPS allowlists and public board URL builders (SSRF guard)."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.job_sources.errors import JobSourceValidationError

GREENHOUSE_HOSTS = frozenset({"boards-api.greenhouse.io", "boards.greenhouse.io"})
LEVER_HOSTS = frozenset({"api.lever.co", "jobs.lever.co"})
ALLOWED_HOSTS = {
    "greenhouse": GREENHOUSE_HOSTS,
    "lever": LEVER_HOSTS,
}

# Public board slugs (Greenhouse token / Lever company), not API secrets.
BOARD_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def assert_https_allowlisted(url: str, source_id: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise JobSourceValidationError("base_url must be HTTPS", path="base_url")
    if parsed.username or parsed.password:
        raise JobSourceValidationError("base_url must not include credentials", path="base_url")
    if parsed.hostname is None:
        raise JobSourceValidationError("base_url host is required", path="base_url")
    allowed = ALLOWED_HOSTS.get(source_id, frozenset())
    host = parsed.hostname.lower()
    if host not in allowed:
        raise JobSourceValidationError(f"host {host} is not allowlisted for {source_id}", path="base_url")
    return url


def parse_board_input(
    source_id: str,
    *,
    token: str | None = None,
    url: str | None = None,
) -> str:
    """Turn a public board token or allowlisted board URL into a tenant_key."""
    raw_token = token.strip() if isinstance(token, str) else ""
    raw_url = url.strip() if isinstance(url, str) else ""
    raw = raw_token or raw_url
    if not raw:
        raise JobSourceValidationError("board token or URL is required", path="boardToken")
    if raw.lower().startswith("http://") or raw.lower().startswith("https://"):
        return _token_from_board_url(source_id, raw)
    return _normalize_board_token(raw, path="boardToken")


def _normalize_board_token(raw: str, *, path: str) -> str:
    token = raw.strip().strip("/")
    if "/" in token or "?" in token or "#" in token or " " in token:
        raise JobSourceValidationError("board token must be a public board slug", path=path)
    if not BOARD_TOKEN_RE.match(token):
        raise JobSourceValidationError("board token must be a public board slug", path=path)
    return token.lower()


def _token_from_board_url(source_id: str, url: str) -> str:
    checked = assert_https_allowlisted(url, source_id)
    parsed = urlparse(checked)
    parts = [part for part in (parsed.path or "").split("/") if part]
    host = (parsed.hostname or "").lower()
    token = ""
    if source_id == "greenhouse":
        if host == "boards-api.greenhouse.io":
            if len(parts) >= 3 and parts[0] == "v1" and parts[1] == "boards":
                token = parts[2]
        elif parts:
            token = parts[0]
        path = "boardUrl"
    else:
        if host == "api.lever.co":
            if len(parts) >= 3 and parts[0] == "v0" and parts[1] == "postings":
                token = parts[2]
        elif parts:
            token = parts[0]
        path = "boardUrl"
    if not token:
        raise JobSourceValidationError("board URL is missing the board token", path=path)
    return _normalize_board_token(token, path=path)


def with_query(url: str, **params: str | int | None) -> str:
    parsed = urlparse(url)
    current = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(current)))


def greenhouse_list_url(tenant_key: str, *, page: int | None = None, content: bool = False) -> str:
    url = f"https://boards-api.greenhouse.io/v1/boards/{tenant_key}/jobs"
    extras: dict[str, str | int | None] = {}
    if page and page > 1:
        extras["page"] = page
    if content:
        extras["content"] = "true"
    return with_query(url, **extras) if extras else url


def greenhouse_detail_url(tenant_key: str, job_id: str) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{tenant_key}/jobs/{job_id}"


def lever_list_url(tenant_key: str, *, skip: int = 0, limit: int = 100) -> str:
    url = f"https://api.lever.co/v0/postings/{tenant_key}"
    return with_query(url, mode="json", skip=skip, limit=limit)


def lever_detail_url(tenant_key: str, job_id: str) -> str:
    return f"https://api.lever.co/v0/postings/{tenant_key}/{job_id}"
