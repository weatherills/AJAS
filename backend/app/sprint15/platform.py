"""Sprint 15 fixtures, seed, docs, CLI, and health helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.sprint14.platform import fixtures_expanded, seed_seniority
from app.sprint15 import VERSION

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "job_boards"


def reset() -> None:
    return None


def fixtures_s15() -> dict[str, Any]:
    snap = fixtures_expanded()
    extra = sorted(p.name for p in FIXTURES.glob("s15_*"))
    return {**snap, "extra": extra, "schema": "ajas.fixtures.v4"}


def seed_v4() -> dict[str, Any]:
    seed = seed_seniority()
    for i, row in enumerate(seed.get("resumes") or []):
        row["tz"] = ["America/Los_Angeles", "America/New_York", "Europe/London", "UTC"][i % 4]
    return {**seed, "timezones": True, "schema": "ajas.seed.v4"}


def ops_guide() -> str:
    return (
        "# Sprint 15 operations\n\n"
        f"Version `{VERSION}`. Optional adapters stay off. Fixture-only parsers.\n"
    )


def api_examples() -> list[dict[str, str]]:
    return [
        {"title": "S15 status", "example": "curl -s localhost:7071/api/v1/s15/status"},
        {"title": "Search jobs", "example": "curl -s 'localhost:7071/api/v1/s15/search?q=python+AND+azure' -H 'Authorization: Bearer ada'"},
        {"title": "Health v4", "example": "curl -s localhost:7071/api/v1/s15/health"},
    ]


def metrics_howto() -> str:
    return "# Observability\n\nRED metrics + SLO burn. Open GET /api/v1/s15/traces.\n"


def data_model() -> str:
    return "jobs ||--o{ aliases : parent\nresumes ||--o{ matches : resume_id\n"


def rollback() -> list[str]:
    return ["git revert HEAD", "set FLAG_* adapters false", "redeploy functions"]


def cli_smoke() -> list[str]:
    return ["scripts/verify_adapters.py indeed", "scripts/ajas.py adapters"]


def cli_reindex() -> list[str]:
    return ["scripts/ajas.py reindex --tenant demo"]
