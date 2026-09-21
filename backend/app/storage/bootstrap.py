"""Create the Cosmos database, containers, and seeds when they are missing.

Called on Functions startup and from `get_database()` so a fresh emulator /
empty account does not require a manual `provision_storage.py` run.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.storage.identity import resolve_cosmos_auth

_READY: dict[str, Any] | None = None


def is_not_found(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in {404, 410}:
        return True
    inner = getattr(exc, "reason", None) or getattr(exc, "error", None)
    if inner is not None and inner is not exc and is_not_found(inner):
        return True
    code = str(getattr(exc, "code", "") or getattr(exc, "sub_status", "") or "").lower()
    message = str(exc).lower()
    needles = ("notfound", "not found", "does not exist", "resourcenotfound", "404")
    return code in {"notfound", "404"} or any(n in message for n in needles)


def reset_bootstrap_state() -> None:
    global _READY
    _READY = None


def _read_database(database: Any) -> None:
    reader = getattr(database, "read", None)
    if callable(reader):
        reader()
        return
    # FakeDatabase has no read(); listing a container client is enough.
    if hasattr(database, "get_container_client"):
        database.get_container_client("schema_migrations")


def ensure_cosmos_database(
    *,
    client: Any | None = None,
    database_name: str | None = None,
    seed: bool | None = None,
    provision: bool = True,
) -> Any:
    """Return the application database, creating it when Cosmos reports 404."""
    settings = get_settings()
    name = database_name or settings.cosmos_database
    if client is None:
        from app.storage.cosmos import get_cosmos_client

        client = get_cosmos_client()
    database = client.get_database_client(name)
    try:
        _read_database(database)
        return database
    except Exception as exc:
        if not settings.cosmos_auto_bootstrap or not is_not_found(exc):
            raise
    created = client.create_database_if_not_exists(id=name)
    if provision:
        from app.storage.provision import provision_cosmos

        provision_cosmos(created)
        do_seed = settings.cosmos_auto_seed if seed is None else seed
        if do_seed:
            from app.storage.dal import CosmosDAL
            from app.storage.seeds import apply_seed

            apply_seed(CosmosDAL(created))
    return created


def bootstrap_on_startup(*, client: Any | None = None, seed: bool | None = None) -> dict[str, Any]:
    """Idempotent startup hook. Never raises — Functions must still boot."""
    global _READY
    if _READY and _READY.get("status") in {"ready", "skipped"} and client is None:
        return _READY
    auth = resolve_cosmos_auth()
    if auth["mode"] == "missing" and client is None:
        _READY = {"status": "skipped", "reason": "cosmos-not-configured", "bootstrapped": False}
        return _READY
    try:
        database = ensure_cosmos_database(client=client, seed=seed)
        from app.storage.catalog import container_catalog

        result = {
            "status": "ready",
            "bootstrapped": True,
            "database": get_settings().cosmos_database,
            "containers": len(container_catalog()),
            "auth": auth["mode"],
        }
        if client is None:
            _READY = result
        return result
    except Exception as exc:  # noqa: BLE001 — startup must not crash the host
        result = {
            "status": "error",
            "bootstrapped": False,
            "error": str(exc)[:240],
            "auth": auth["mode"],
        }
        if client is None:
            _READY = result
        return result
