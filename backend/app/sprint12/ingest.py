"""Sitemap crawler, robots/rate policy, proxy failover, vector/queue circuit."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

from app.job_sources.circuit import allow as source_allow, record_status, reset as reset_source
from app.job_sources import proxies as proxy_pool

_RATE: dict[str, list[float]] = {}
_CIRCUIT: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _RATE.clear()
    _CIRCUIT.clear()
    reset_source()
    proxy_pool.reset()


def parse_sitemap(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text.strip() for el in root.findall(".//sm:loc", ns) if el.text]
    if not locs:
        locs = [el.text.strip() for el in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc") if el.text]
    if not locs:
        locs = [el.text.strip() for el in root.findall(".//loc") if el.text]
    return [url for url in locs if url.startswith("http")]


def board_jobs_from_urls(urls: list[str], *, source: str) -> list[dict[str, Any]]:
    jobs = []
    for url in urls:
        path = urlparse(url).path.rstrip("/").split("/")[-1]
        jobs.append(
            {
                "source": source,
                "source_posting_id": path or url,
                "url": url,
                "title": path.replace("-", " ").title() or "Role",
            }
        )
    return jobs


def robots_rate_policy(domain: str, *, crawl_delay: float | None = None) -> dict[str, Any]:
    host = urlparse(domain).netloc or domain
    delay = 1.0 if crawl_delay is None else float(crawl_delay)
    return {"domain": host, "crawlDelaySec": delay, "respectRobots": True, "maxConcurrent": 1}


def allow_domain_request(domain: str, *, now: float | None = None, min_interval: float = 1.0) -> bool:
    clock = now if now is not None else time.monotonic()
    host = urlparse(domain).netloc or domain
    stamps = [ts for ts in _RATE.get(host, []) if clock - ts < 60]
    last = stamps[-1] if stamps else None
    if last is not None and clock - last < min_interval:
        _RATE[host] = stamps
        return False
    stamps.append(clock)
    _RATE[host] = stamps
    return True


def proxy_failover(urls: list[str], *, unhealthy: set[str] | None = None) -> str | None:
    proxy_pool.reset()
    for url in urls:
        proxy_pool.add(url)
    for url in unhealthy or set():
        proxy_pool.record_result(url, False, fail_after=1)
    nxt = proxy_pool.next_proxy()
    return nxt.url if nxt else None


def vector_circuit(name: str, *, ok: bool) -> dict[str, Any]:
    snap = record_status(name, 200 if ok else 503)
    return {"name": name, "open": snap.disabled, "allow": source_allow(name)}


def queue_circuit(name: str, *, depth: int, max_depth: int = 1000) -> dict[str, Any]:
    open_ = depth >= max_depth
    _CIRCUIT[name] = {"open": open_, "depth": depth, "max": max_depth}
    return {"name": name, "open": open_, "allow": not open_, "depth": depth}


def greenhouse_board_jobs(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    rows = []
    for job in jobs or []:
        company = job.get("company")
        depts = job.get("departments")
        if not company and isinstance(depts, list) and depts:
            company = depts[0].get("name")
        rows.append(
            {
                "source": "greenhouse",
                "source_posting_id": str(job.get("id") or job.get("absolute_url") or ""),
                "title": job.get("title") or job.get("name"),
                "url": job.get("absolute_url") or job.get("url"),
                "company": company,
            }
        )
    return rows


def lever_board_jobs(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    jobs = payload.get("data") if isinstance(payload, dict) else payload
    rows = []
    for job in jobs or []:
        cats = job.get("categories") or {}
        rows.append(
            {
                "source": "lever",
                "source_posting_id": str(job.get("id") or ""),
                "title": job.get("text") or job.get("title"),
                "url": job.get("hostedUrl") or job.get("url"),
                "company": cats.get("team") or job.get("company"),
            }
        )
    return rows
