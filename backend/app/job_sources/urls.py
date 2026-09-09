"""HTTPS allowlists and public board URL builders (SSRF guard)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.job_sources.errors import JobSourceValidationError

GREENHOUSE_HOSTS = frozenset({"boards-api.greenhouse.io", "boards.greenhouse.io"})
LEVER_HOSTS = frozenset({"api.lever.co", "jobs.lever.co"})
ALLOWED_HOSTS = {
    "greenhouse": GREENHOUSE_HOSTS,
    "lever": LEVER_HOSTS,
}


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
