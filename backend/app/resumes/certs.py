"""Certification extractor v2 — expand common cert patterns."""

from __future__ import annotations

import re

PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\baws certified (solutions architect|developer|sysops)\b", "aws"),
    (r"\b(cka|ckad|cks)\b", "kubernetes"),
    (r"\bazure (administrator|developer|solutions architect)\b", "azure"),
    (r"\bgoogle (professional )?cloud architect\b", "gcp"),
    (r"\b(pmp|cissp|ccna|ccnp|comptia security\+|security\+)\b", "security"),
    (r"\b(snowflake|databricks|dbt) certified\b", "data"),
)


def extract_certs(text: str) -> list[dict[str, str]]:
    hay = text or ""
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern, family in PATTERNS:
        for match in re.finditer(pattern, hay, re.I):
            label = match.group(0)
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append({"name": label, "family": family})
    return found
