"""Pinned Cosmos SDK version, canary import, and rollback notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PINNED = "4.17.1"
REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"


def pinned_version() -> str:
    return PINNED


def requirements_pin() -> str:
    text = REQUIREMENTS.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lower().startswith("azure-cosmos"):
            return line.strip()
    return ""


def installed_version() -> str:
    import importlib.metadata

    return importlib.metadata.version("azure-cosmos")


def canary() -> dict[str, Any]:
    from azure.cosmos import CosmosClient  # noqa: F401

    from app.storage.dal import CosmosDAL
    from app.storage.testing import FakeDatabase

    dal = CosmosDAL(FakeDatabase())
    dal.upsert("users", {"id": "canary", "email": "canary@ajas.dev"})
    row = dal.read("users", "canary", partition_key="canary")
    pin = requirements_pin()
    installed = installed_version()
    return {
        "schema": "ajas.cosmos.sdk.canary.v1",
        "pinned": PINNED,
        "requirement": pin,
        "installed": installed,
        "ok": pin.endswith(PINNED) and installed == PINNED and row["id"] == "canary",
        "rollback": "Revert azure-cosmos pin in backend/requirements.txt and redeploy Functions.",
    }
