"""Credential resolution for Cosmos, Blob, and Queue.

Never log or return secret values. Connection strings and keys stay in env;
production uses DefaultAzureCredential (managed identity) against an account URL.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings


def resolve_cosmos_auth(settings: Settings | None = None) -> dict[str, str]:
    cfg = settings or get_settings()
    if (cfg.cosmos_connection_string or "").strip():
        return {"mode": "connection_string", "secret": "env:COSMOS_CONNECTION_STRING"}
    if (cfg.cosmos_endpoint or "").strip() and (cfg.cosmos_key or "").strip():
        return {"mode": "key", "endpoint": cfg.cosmos_endpoint, "secret": "env:COSMOS_KEY"}
    if (cfg.cosmos_endpoint or "").strip():
        return {"mode": "aad", "endpoint": cfg.cosmos_endpoint, "secret": "DefaultAzureCredential"}
    return {"mode": "missing", "secret": ""}


def resolve_blob_auth(settings: Settings | None = None) -> dict[str, str]:
    cfg = settings or get_settings()
    if (cfg.blob_connection_string or "").strip():
        return {"mode": "connection_string", "secret": "env:BLOB_CONNECTION_STRING"}
    if (cfg.blob_account_url or "").strip():
        return {"mode": "aad", "endpoint": cfg.blob_account_url, "secret": "DefaultAzureCredential"}
    return {"mode": "missing", "secret": ""}


def resolve_queue_auth(settings: Settings | None = None) -> dict[str, str]:
    cfg = settings or get_settings()
    if (cfg.queue_connection_string or "").strip():
        return {"mode": "connection_string", "secret": "env:QUEUE_CONNECTION_STRING"}
    if (cfg.queue_account_url or "").strip():
        return {"mode": "aad", "endpoint": cfg.queue_account_url, "secret": "DefaultAzureCredential"}
    return {"mode": "missing", "secret": ""}


def default_azure_credential() -> Any:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def assert_no_plaintext_secrets(payload: dict[str, Any]) -> None:
    """Guard rails for logs / provision output: never echo keys."""
    banned = ("AccountKey=", "SharedAccessSignature=", "sk-", "cosmos_key")
    blob = json_dumps_lower(payload)
    for needle in banned:
        if needle.lower() in blob:
            raise ValueError("refusing to emit a secret in connection metadata")


def json_dumps_lower(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str).lower()
