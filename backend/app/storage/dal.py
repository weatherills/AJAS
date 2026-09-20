"""Reusable Cosmos CRUD helpers: retries, RU logging, continuation pages."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.metrics import increment
from app.storage.chaos import maybe_raise
from app.storage.query_lint import enforce_lint, lint_query, record_profile

RETRY_STATUSES = frozenset({429, 408, 503})
DEFAULT_RETRIES = 4
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class ConflictError(RuntimeError):
    """Optimistic concurrency: If-Match etag did not match the stored document."""

    status_code = 412


class ContainerClient(Protocol):
    def create_item(self, body: dict[str, Any], **kwargs: Any) -> Any: ...

    def read_item(self, item: str, partition_key: Any, **kwargs: Any) -> Any: ...

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> Any: ...

    def replace_item(self, item: str, body: dict[str, Any], **kwargs: Any) -> Any: ...

    def delete_item(self, item: str, partition_key: Any, **kwargs: Any) -> Any: ...

    def query_items(self, query: str, **kwargs: Any) -> Any: ...


class DatabaseClient(Protocol):
    def get_container_client(self, name: str) -> ContainerClient: ...


@dataclass
class Page:
    items: list[dict[str, Any]]
    continuation: str | None
    request_charge: float


def _charge_of(result: Any) -> float:
    headers = getattr(result, "headers", None) or getattr(result, "_headers", None) or {}
    if isinstance(headers, dict):
        raw = headers.get("x-ms-request-charge") or headers.get("x-ms-request-charge".title())
        try:
            return float(raw or 0)
        except (TypeError, ValueError):
            return 0.0
    return float(getattr(result, "request_charge", 0) or 0)


def _status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    inner = getattr(exc, "reason", None)
    if inner is not None and inner is not exc:
        return _status_of(inner)
    return None


def _is_retryable(exc: BaseException) -> bool:
    status = _status_of(exc)
    if status in RETRY_STATUSES:
        return True
    name = type(exc).__name__.lower()
    return "throttl" in name or "timeout" in name or "serviceunavailable" in name


def with_retry(fn: Callable[[], Any], *, retries: int = DEFAULT_RETRIES, delay: float = 0.05) -> Any:
    last: BaseException | None = None
    wait = delay
    for attempt in range(max(1, retries)):
        try:
            maybe_raise()
            return fn()
        except Exception as exc:  # noqa: BLE001 — SDK raises a mix of types
            last = exc
            if attempt >= retries - 1 or not _is_retryable(exc):
                raise
            increment("cosmos.throttles")
            time.sleep(wait)
            wait *= 2
    assert last is not None
    raise last


class CosmosDAL:
    """Thin SDK wrapper used by feature stores and the provisioner."""

    def __init__(self, database: DatabaseClient, *, retries: int = DEFAULT_RETRIES) -> None:
        self._database = database
        self._retries = retries

    def container(self, name: str) -> ContainerClient:
        return self._database.get_container_client(name)

    def _run(self, fn: Callable[[], Any]) -> Any:
        result = with_retry(fn, retries=self._retries)
        charge = _charge_of(result)
        if charge:
            increment("cosmos.ru", charge)
        increment("cosmos.ops")
        return result

    def create(self, container: str, body: dict[str, Any]) -> dict[str, Any]:
        client = self.container(container)
        result = self._run(lambda: client.create_item(body=body))
        return dict(result) if result is not None else dict(body)

    def read(self, container: str, item_id: str, *, partition_key: Any, redact: bool = False) -> dict[str, Any]:
        client = self.container(container)
        result = self._run(lambda: client.read_item(item=item_id, partition_key=partition_key))
        payload = dict(result)
        if redact:
            from app.storage.pii import redact as redact_doc

            return redact_doc(container, payload)
        return payload

    def upsert(self, container: str, body: dict[str, Any]) -> dict[str, Any]:
        client = self.container(container)
        result = self._run(lambda: client.upsert_item(body=body))
        return dict(result) if result is not None else dict(body)

    def replace(
        self,
        container: str,
        item_id: str,
        body: dict[str, Any],
        *,
        etag: str | None = None,
    ) -> dict[str, Any]:
        client = self.container(container)

        def _go() -> Any:
            kwargs: dict[str, Any] = {"item": item_id, "body": body}
            if etag:
                kwargs["etag"] = etag
                kwargs["if_match"] = etag
            return client.replace_item(**kwargs)

        result = self._run(_go)
        return dict(result) if result is not None else dict(body)

    def delete(self, container: str, item_id: str, *, partition_key: Any) -> None:
        client = self.container(container)
        self._run(lambda: client.delete_item(item=item_id, partition_key=partition_key))

    def query(
        self,
        container: str,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: Any | None = None,
        continuation: str | None = None,
        max_items: int = DEFAULT_PAGE_SIZE,
        allow_cross_partition: bool = False,
        redact: bool = False,
    ) -> Page:
        lint = lint_query(
            container,
            query,
            partition_key=partition_key,
            allow_cross_partition=allow_cross_partition,
        )
        enforce_lint(lint)
        size = max(1, min(int(max_items), MAX_PAGE_SIZE))
        client = self.container(container)

        def _go() -> Any:
            kwargs: dict[str, Any] = {
                "query": query,
                "max_item_count": size,
            }
            if parameters:
                kwargs["parameters"] = parameters
            if partition_key is not None:
                kwargs["partition_key"] = partition_key
            else:
                kwargs["enable_cross_partition_query"] = True
            if continuation:
                kwargs["continuation"] = continuation
            return client.query_items(**kwargs)

        result = self._run(_go)
        items, token, charge = _materialize_query(result, size)
        if charge:
            increment("cosmos.ru", charge)
        record_profile(container, query, ru=charge or 1.0, partition_key=partition_key)
        if redact:
            from app.storage.pii import redact as redact_doc

            items = [redact_doc(container, item) for item in items]
        return Page(items=items, continuation=token, request_charge=charge)


def _materialize_query(result: Any, size: int) -> tuple[list[dict[str, Any]], str | None, float]:
    charge = _charge_of(result)
    continuation = getattr(result, "continuation_token", None) or getattr(result, "continuation", None)
    if isinstance(result, list):
        items = [dict(item) for item in result[:size]]
        token = continuation
        if token is None and len(result) > size:
            token = f"offset:{size}"
        return items, token, charge
    items: list[dict[str, Any]] = []
    iterator = iter(result)
    for _ in range(size):
        try:
            items.append(dict(next(iterator)))
        except StopIteration:
            break
    if continuation is None:
        continuation = getattr(iterator, "continuation_token", None)
    return items, continuation, charge
