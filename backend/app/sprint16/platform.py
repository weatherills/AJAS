"""Sprint 16 fixtures, seed, docs, CLI, and health helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.sprint15.platform import fixtures_s15, seed_v4
from app.sprint16 import VERSION

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "job_boards"


def reset() -> None:
    return None


def fixtures_s16() -> dict[str, Any]:
    snap = fixtures_s15()
    extra = sorted(p.name for p in FIXTURES.glob("s16_*"))
    return {**snap, "extra": extra, "schema": "ajas.fixtures.v5"}


def seed_v5() -> dict[str, Any]:
    seed = seed_v4()
    locales = ["en-US", "en-GB", "fr-FR", "de-DE"]
    for i, row in enumerate(seed.get("resumes") or []):
        row["locale"] = locales[i % len(locales)]
    return {**seed, "locales": True, "schema": "ajas.seed.v5"}


def ops_guide() -> str:
    return (
        "# Sprint 16 operations\n\n"
        f"Version `{VERSION}`. Optional adapters stay off. Fixture-only parsers.\n"
    )


def api_examples() -> list[dict[str, str]]:
    return [
        {"title": "S16 status", "example": "curl -s localhost:7071/api/v1/s16/status"},
        {"title": "Search jobs", "example": "curl -s 'localhost:7071/api/v1/s16/search?q=%22python%22+NOT+java' -H 'Authorization: Bearer ada'"},
        {"title": "Health v5", "example": "curl -s localhost:7071/api/v1/s16/health"},
    ]


def metrics_howto() -> str:
    return "# Observability\n\nUSE metrics + error budget remaining. Open GET /api/v1/s16/traces.\n"


def data_model() -> str:
    return "jobs ||--o{ brands : dba\nresumes ||--o{ matches : resume_id\n"


def rollback() -> list[str]:
    return ["git revert HEAD", "set FLAG_* adapters false", "redeploy functions"]


def cli_smoke() -> list[str]:
    return ["scripts/verify_adapters.py builtin", "scripts/ajas.py adapters"]


def cli_reindex() -> list[str]:
    return ["scripts/ajas.py reindex --tenant demo"]
