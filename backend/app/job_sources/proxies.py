"""Rotating outbound proxy pool with health checks.

Live scraping is out of the Job Source PRD. This pool is used only for
allowlisted HTTPS adapter calls; an empty pool means direct egress.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Proxy:
    url: str
    failures: int = 0
    healthy: bool = True


_POOL: list[Proxy] = []
_INDEX = 0


def reset() -> None:
    global _INDEX
    _POOL.clear()
    _INDEX = 0


def add(url: str) -> Proxy:
    proxy = Proxy(url=url.strip())
    _POOL.append(proxy)
    return proxy


def next_proxy() -> Proxy | None:
    global _INDEX
    healthy = [item for item in _POOL if item.healthy]
    if not healthy:
        return None
    proxy = healthy[_INDEX % len(healthy)]
    _INDEX += 1
    return proxy


def record_result(url: str, ok: bool, *, fail_after: int = 3) -> Proxy | None:
    for proxy in _POOL:
        if proxy.url != url:
            continue
        if ok:
            proxy.failures = 0
            proxy.healthy = True
        else:
            proxy.failures += 1
            if proxy.failures >= fail_after:
                proxy.healthy = False
        return proxy
    return None


def snapshot() -> dict[str, object]:
    return {
        "size": len(_POOL),
        "healthy": sum(1 for item in _POOL if item.healthy),
        "urls": [item.url for item in _POOL if item.healthy],
    }
