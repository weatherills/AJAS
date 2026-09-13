"""Sprint 14 fixtures, seed, docs, CLI, and health helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.sprint13.platform import fixtures_v3, seed_v3
from app.sprint14 import VERSION

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "job_boards"


def reset() -> None:
    return None


def fixtures_expanded() -> dict[str, Any]:
    snap = fixtures_v3()
    extra = sorted(p.name for p in FIXTURES.glob("s14_*"))
    return {**snap, "extra": extra, "schema": "ajas.fixtures.v3"}


def seed_seniority() -> dict[str, Any]:
    seed = seed_v3(n_resumes=6, n_jobs=8)
    for i, row in enumerate(seed["resumes"]):
        row["seniority"] = ["intern", "junior", "mid", "senior", "staff", "principal"][i % 6]
        row["remote"] = i % 2 == 0
    return {**seed, "bySeniority": True}


def ops_guide() -> str:
    return (
        "# Sprint 14 operations\n\n"
        f"Version `{VERSION}`. Optional adapters stay off. Fixture-only parsers.\n"
    )


def api_examples() -> list[dict[str, str]]:
    return [
        {"title": "S14 status", "example": "curl -s localhost:7071/api/v1/s14/status"},
        {"title": "Search jobs", "example": "curl -s 'localhost:7071/api/v1/s14/search?q=python' -H 'Authorization: Bearer ada'"},
        {"title": "Health v3", "example": "curl -s localhost:7071/api/v1/s14/health"},
    ]


def metrics_howto() -> str:
    return "# Observability\n\nPropagate trace IDs ingest→apply. Open GET /api/v1/s14/traces.\n"


def data_model() -> str:
    return "jobs ||--o{ matches : scores\nresumes ||--o{ matches : resume_id\n"


def rollback() -> list[str]:
    return ["git revert HEAD", "set FLAG_* adapters false", "redeploy functions"]


def cli_reindex() -> list[str]:
    return ["scripts/ajas.py reindex", "scripts/ajas.py seed"]


def cli_verify() -> list[str]:
    return ["scripts/verify_adapters.py ziprecruiter", "scripts/ajas.py adapters"]
