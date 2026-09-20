"""Cosmos key rotation with client hot-reload."""

from __future__ import annotations

from typing import Any

from app.secrets_rotate import fingerprint, rotate
from app.storage.cosmos import get_cosmos_client, reset_cosmos_client


def reset_cosmos_clients() -> None:
    reset_cosmos_client()


def rotate_cosmos_key(new_key: str, *, previous: str | None = None) -> dict[str, Any]:
    result = rotate("COSMOS_KEY", new_key, previous=previous)
    reset_cosmos_clients()
    result["hotReload"] = True
    result["reminder"] = "quarterly"
    result["runbook"] = "docs/cosmos-ops.md#key-rotation"
    result["fingerprint"] = fingerprint(new_key)
    return result
