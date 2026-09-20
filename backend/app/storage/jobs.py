"""Scheduled retention + blob lifecycle execution."""

from __future__ import annotations

from typing import Any

from app.storage.blob_layout import blob_container_names, lifecycle_rules
from app.storage.retention import DocumentStore, apply_retention, retention_plan


def run_retention_job(
    store: DocumentStore | None,
    *,
    jobs: list[dict[str, Any]] | None = None,
    emails: list[dict[str, Any]] | None = None,
    matches: list[dict[str, Any]] | None = None,
    resumes: list[dict[str, Any]] | None = None,
    applications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    plan = retention_plan(
        jobs=jobs,
        emails=emails,
        matches=matches,
        resumes=resumes,
        applications=applications,
    )
    result = apply_retention(store, plan)
    return {
        "schema": "ajas.retention.job.v1",
        "plan": plan,
        "result": result,
        "blobLifecycle": lifecycle_rules(),
        "blobContainers": list(blob_container_names()),
    }
