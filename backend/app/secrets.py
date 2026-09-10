"""Optional Azure Key Vault hydration. Local/dev stays env-only when KEY_VAULT_URI is unset."""

from __future__ import annotations

import logging
import os

log = logging.getLogger("ajas")

_SECRET_ENV = (
    "AZURE_OPENAI_API_KEY",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_CLIENT_ID",
    "COSMOS_CONNECTION_STRING",
    "AUTH_JWT_SECRET",
    "AJAS_SESSION_SECRET",
    "MAIL_BOUNCE_WEBHOOK_SECRET",
    "AUTO_APPLY_WEBHOOK_SECRET",
    "SETTINGS_TOKEN_KEY",
    "GREENHOUSE_SUBMIT_API_KEY",
    "LEVER_SUBMIT_API_KEY",
)


def hydrate_from_key_vault() -> None:
    uri = (os.environ.get("KEY_VAULT_URI") or os.environ.get("AZURE_KEY_VAULT_URI") or "").strip()
    if not uri:
        return
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        log.warning("ajas.secrets Key Vault URI set but azure-identity/keyvault packages are missing")
        return
    try:
        client = SecretClient(vault_url=uri, credential=DefaultAzureCredential())
    except Exception as exc:
        log.warning("ajas.secrets could not open Key Vault: %s", exc)
        return
    for name in _SECRET_ENV:
        if (os.environ.get(name) or "").strip():
            continue
        secret_name = name.lower().replace("_", "-")
        try:
            value = client.get_secret(secret_name).value
        except Exception:
            continue
        if value:
            os.environ[name] = value
            log.info("ajas.secrets hydrated %s from Key Vault", name)
