"""Shared listing field helpers for extra-board ingest connectors."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from app.integrations.linkedin_spec import listing_dedupe_key, listing_visibility
from app.job_sources.keys import canonical_id_for


def nested_text(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        nested = (
            value.get("name")
            or value.get("text")
            or value.get("label")
            or value.get("display")
            or value.get("formatted")
        )
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return ""


def xml_child_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return str(child.text).strip()


def join_location(*parts: str) -> str:
    return ", ".join(part for part in parts if part and part.strip())


def extract_mapped_field(job: dict[str, Any], spec: dict[str, Any], *, source_key: str) -> str:
    keys = (spec[source_key], *spec.get("aliases", ()))
    for key in keys:
        text = nested_text(job.get(key))
        if text:
            return text
        if key == "location" and isinstance(job.get("location"), dict):
            loc = job["location"]
            text = join_location(
                nested_text(loc.get("city")),
                nested_text(loc.get("state") or loc.get("admin1Code") or loc.get("region")),
                nested_text(loc.get("country") or loc.get("countryCode")),
            ) or nested_text(loc.get("display")) or nested_text(loc.get("name"))
            if text:
                return text
    fallback = spec.get("fallback")
    if fallback in {None, "canonical_id[:12]", "public"}:
        return ""
    return str(fallback or "")


def finish_mapped_job(mapped: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    vis = listing_visibility(job)
    posted = mapped.get("postedAt") or ""
    title = mapped.get("title") or ""
    company = mapped.get("company") or ""
    location = mapped.get("location") or ""
    mapped["visibility"] = vis["reason"]
    mapped["visible"] = vis["visible"]
    mapped["listingKey"] = listing_dedupe_key(
        title=title, company=company, location=location, posted_at=posted
    )
    if not mapped.get("sourcePostingId"):
        mapped["sourcePostingId"] = canonical_id_for(mapped["listingKey"])[:12]
    return mapped
