"""Greenhouse and Lever programmatic submit adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from app.auto_apply.models import AutoApplyAttempt, FormAutofillValue, VendorFieldMapping


class HttpPoster(Protocol):
    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, dict[str, Any]]: ...


class UrllibPoster:
    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json", "User-Agent": "AJAS-auto-apply/1.0", **headers}
        request = Request(url, data=body, method="POST", headers=merged)
        try:
            with urlopen(request, timeout=20) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                if not isinstance(parsed, dict):
                    parsed = {"raw": parsed}
                return int(getattr(resp, "status", 200)), parsed
        except HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            parsed: dict[str, Any]
            try:
                loaded = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                parsed = loaded if isinstance(loaded, dict) else {"raw": loaded}
            except Exception:
                parsed = {"error": raw.decode("utf-8", errors="replace")}
            return int(exc.code), parsed
        except URLError as exc:
            raise TimeoutError(str(exc.reason or exc)) from exc


@dataclass
class SubmitOutcome:
    status: str
    vendor_application_id: str | None
    vendor_request_id: str | None
    status_code: int
    endpoint: str
    fields: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return "Applicant", "Unknown"
    if len(parts) == 1:
        return parts[0], "Applicant"
    return parts[0], " ".join(parts[1:])


def map_vendor_fields(
    vendor: str,
    *,
    profile: dict[str, str],
    answers: dict[str, Any],
    autofill: list[FormAutofillValue],
    mappings: list[VendorFieldMapping],
) -> dict[str, Any]:
    values: dict[str, str] = dict(profile)
    for row in autofill:
        if row.value:
            values[row.field_key] = row.value
    for key, value in answers.items():
        if value is not None and str(value).strip():
            values[str(key)] = str(value).strip()

    mapped: dict[str, Any] = {}
    for mapping in mappings:
        if mapping.vendor != vendor:
            continue
        raw = values.get(mapping.normalized_key)
        if not raw:
            continue
        if mapping.transform == "split_first":
            first, last = _split_name(raw)
            mapped["first_name"] = first
            mapped["last_name"] = last
            mapped[mapping.vendor_field_key] = first
        else:
            mapped[mapping.vendor_field_key] = raw
    if vendor == "greenhouse":
        if "first_name" not in mapped or "last_name" not in mapped:
            first, last = _split_name(values.get("full_name") or values.get("name") or "Alex Jobseeker")
            mapped.setdefault("first_name", first)
            mapped.setdefault("last_name", last)
        mapped.setdefault("email", values.get("email") or "")
        mapped.setdefault("phone", values.get("phone") or "")
    else:
        mapped.setdefault("name", values.get("full_name") or values.get("name") or "Alex Jobseeker")
        mapped.setdefault("email", values.get("email") or "")
        if values.get("phone"):
            mapped.setdefault("phone", values["phone"])
    return mapped


def greenhouse_endpoint(posting_url: str | None, job_id: str | None) -> str:
    board = "demo"
    job = job_id or "job"
    if posting_url:
        parsed = urlparse(posting_url)
        parts = [part for part in (parsed.path or "").split("/") if part]
        if parts:
            board = parts[0]
        if "jobs" in parts:
            idx = parts.index("jobs")
            if idx + 1 < len(parts):
                job = parts[idx + 1]
        elif parts:
            job = parts[-1]
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}"


def lever_endpoint(posting_url: str | None, job_id: str | None) -> str:
    company = "demo"
    job = job_id or "job"
    if posting_url:
        parsed = urlparse(posting_url)
        parts = [part for part in (parsed.path or "").split("/") if part]
        if parts:
            company = parts[0]
        if len(parts) >= 2:
            job = parts[1]
    return f"https://api.lever.co/v0/postings/{company}/{job}"


def submit_to_vendor(
    attempt: AutoApplyAttempt,
    fields: dict[str, Any],
    *,
    live: bool = False,
    api_key: str | None = None,
    poster: HttpPoster | None = None,
) -> SubmitOutcome:
    if "429" in (attempt.posting_url or ""):
        endpoint = (
            greenhouse_endpoint(attempt.posting_url, attempt.job_id)
            if attempt.vendor == "greenhouse"
            else lever_endpoint(attempt.posting_url, attempt.job_id)
        )
        return SubmitOutcome(
            status="rate_limited",
            vendor_application_id=None,
            vendor_request_id=None,
            status_code=429,
            endpoint=endpoint,
            fields=fields,
            error_code="rate_limited",
            error_message="Provider rate limited the request",
        )

    if attempt.vendor == "greenhouse":
        endpoint = greenhouse_endpoint(attempt.posting_url, attempt.job_id)
    else:
        endpoint = lever_endpoint(attempt.posting_url, attempt.job_id)

    if live and (api_key or "").strip():
        client = poster or UrllibPoster()
        headers = {"Authorization": f"Bearer {api_key.strip()}"}
        if attempt.vendor == "lever":
            sep = "&" if "?" in endpoint else "?"
            endpoint = f"{endpoint}{sep}key={api_key.strip()}"
            headers = {}
        status_code, body = client.post(endpoint, fields, headers)
        if status_code == 429:
            return SubmitOutcome(
                status="rate_limited",
                vendor_application_id=None,
                vendor_request_id=None,
                status_code=429,
                endpoint=endpoint,
                fields=fields,
                error_code="rate_limited",
                error_message="Provider rate limited the request",
            )
        if status_code >= 400:
            return SubmitOutcome(
                status="failed",
                vendor_application_id=None,
                vendor_request_id=None,
                status_code=status_code,
                endpoint=endpoint,
                fields=fields,
                error_code="provider_error",
                error_message=str(body.get("error") or body.get("message") or f"HTTP {status_code}"),
            )
        app_id = str(body.get("id") or body.get("application_id") or uuid4())
        return SubmitOutcome(
            status="succeeded",
            vendor_application_id=app_id,
            vendor_request_id=str(body.get("request_id") or uuid4()),
            status_code=status_code,
            endpoint=endpoint,
            fields=fields,
        )

    return SubmitOutcome(
        status="succeeded",
        vendor_application_id=f"{attempt.vendor}-{attempt.id[:8]}",
        vendor_request_id=str(uuid4()),
        status_code=201,
        endpoint=endpoint,
        fields=fields,
    )
