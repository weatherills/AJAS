"""Job Source crawl application service (Backend PRD)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from app.config import get_settings as get_app_settings
from app.job_sources.blobs import BlobStore, InMemoryBlobStore
from app.job_sources.errors import (
    JobSourceNotFoundError,
    JobSourceRateLimitedError,
    JobSourceValidationError,
)
from app.job_sources.events import CrawlEventLog
from app.job_sources.feed import feed_cards, filter_cards
from app.job_sources.http import FetchResponse, HttpFetcher, UrllibFetcher
from app.job_sources.keys import parse_ts, utc_now
from app.job_sources.models import SourceFetchRun, SourceTenant
from app.job_sources.normalize import (
    greenhouse_job,
    greenhouse_list_jobs,
    lever_job,
    lever_list_jobs,
    payload_dumps,
)
from app.job_sources.queues import InMemoryJobQueue, JobQueue
from app.job_sources.store import JobSourceStore, get_job_source_store
from app.job_sources.urls import (
    assert_https_allowlisted,
    greenhouse_detail_url,
    greenhouse_list_url,
    lever_detail_url,
    lever_list_url,
    parse_board_input,
    with_query,
)

RETRYABLE_STATUS = {429, 503, 504}


def _resume_rank_text(resume: Any) -> str:
    parts: list[str] = []
    contact = getattr(resume, "contact", None)
    if contact:
        parts.extend([p for p in (contact.full_name, contact.email) if p])
    parts.extend(skill.name for skill in getattr(resume, "skills", []) or [] if getattr(skill, "name", None))
    for exp in getattr(resume, "experiences", []) or []:
        parts.extend([p for p in (exp.title, exp.company, exp.description) if p])
    haystack = " ".join(parts)
    return haystack or (getattr(resume, "text_preview", None) or "")
MAX_PAGES = 100
MAX_GET_RETRIES_TRANSIENT = 5
MAX_GET_RETRIES_NETWORK = 3
LIST_ENDPOINT = "list"
DETAIL_ENDPOINT = "detail"
Sleeper = Callable[[float], None]


def _sleep_noop(_seconds: float) -> None:
    return None


def source_display_name(source_id: str) -> str:
    return "Greenhouse" if source_id == "greenhouse" else "Lever"


def source_not_configured_message(source_id: str) -> str:
    name = source_display_name(source_id)
    return (
        f"{name} is not configured. Add a board token before turning this source on, "
        "or Job Feed stays empty."
    )


def public_crawl_error(source_id: str, error: str | None, *, board: str | None = None) -> str:
    """Stable, user-facing crawl failure copy for the Job Feed status bar."""
    name = source_display_name(source_id)
    board_label = f' "{board}"' if (board or "").strip() else ""
    raw = (error or "").strip()
    lowered = raw.lower()
    if raw.startswith("Greenhouse ") or raw.startswith("Lever ") or raw.startswith("Could not reach "):
        return raw
    if raw.isdigit():
        code = int(raw)
        if code == 404:
            return f"{name} board{board_label} was not found. Check the board token or URL."
        if code in {429, 503, 504}:
            return f"{name} is temporarily unavailable (HTTP {code}). Retry shortly."
        return f"{name} returned HTTP {code}."
    if not raw or raw == "listing fetch failed":
        return f"{name} listing fetch failed. The board{board_label} may be unreachable."
    if raw in {"404", "not found"} or "http 404" in lowered or "not found" in lowered:
        return f"{name} board{board_label} was not found. Check the board token or URL."
    if any(
        token in lowered
        for token in (
            "timed out",
            "timeout",
            "unreachable",
            "name or service not known",
            "failed to resolve",
            "connection refused",
            "temporarily unavailable",
        )
    ):
        return f"Could not reach {name}{board_label}. The board may be unreachable."
    if lowered.startswith("http "):
        return f"{name} returned {raw}."
    return f"{name} fetch failed: {raw}"


def api_status(status: str) -> str:
    return "partial" if status == "partial_success" else status


def run_payload(run: SourceFetchRun, *, tenant_id: str | None = None) -> dict:
    return {
        "runId": run.id,
        "sourceId": tenant_id or run.source_tenant_id,
        "tenantId": run.source_tenant_id,
        "status": api_status(run.status),
        "fetchedCount": run.fetched_count,
        "upsertCount": run.upsert_count,
        "noopCount": run.noop_count,
        "errorCount": run.error_count,
        "errorSummary": run.error_summary,
        "startedAt": run.started_at,
        "finishedAt": run.finished_at,
    }


def tenant_payload(tenant: SourceTenant) -> dict:
    return {
        "id": tenant.id,
        "sourceId": tenant.source_id,
        "tenantKey": tenant.tenant_key,
        "enabled": tenant.enabled,
    }


def _board_payload(
    tenant: SourceTenant,
    *,
    status: str = "ok",
    error_message: str | None = None,
    last_sync_at: str | None = None,
) -> dict:
    return {
        "tenantKey": tenant.tenant_key,
        "enabled": tenant.enabled,
        "status": status,
        "errorMessage": error_message,
        "lastSyncAt": last_sync_at,
    }


class CrawlService:
    def __init__(
        self,
        store: JobSourceStore | None = None,
        queue: JobQueue | None = None,
        blobs: BlobStore | None = None,
        fetcher: HttpFetcher | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self.store = store or get_job_source_store()
        self.queue = queue or InMemoryJobQueue()
        self.blobs = blobs or InMemoryBlobStore()
        self.fetcher = fetcher or UrllibFetcher()
        self.sleeper = sleeper or _sleep_noop
        self.events = CrawlEventLog()

    def enqueue_crawl(self, source_id: str) -> dict:
        tenants = self._resolve_tenants(source_id)
        if not tenants:
            if source_id in {"greenhouse", "lever"}:
                return {"runs": [], "status": "skipped", "reason": "not_configured"}
            raise JobSourceNotFoundError(source_id)
        cfg = get_app_settings()
        runs = []
        for tenant in tenants:
            if not tenant.enabled:
                raise JobSourceValidationError("tenant is disabled", path="enabled")
            run = self.store.start_run(tenant.id, status="queued")
            self.queue.enqueue(cfg.crawl_runs_queue, {"tenantId": tenant.id, "runId": run.id})
            runs.append(run_payload(run, tenant_id=tenant.id))
        body = {"runs": runs, "status": "queued"}
        if len(runs) == 1:
            body["runId"] = runs[0]["runId"]
        return body

    def enqueue_crawl_tenant(self, source_id: str, tenant_key: str) -> dict:
        if source_id not in {"greenhouse", "lever"}:
            raise JobSourceNotFoundError(source_id)
        key = (tenant_key or "").strip()
        if not key:
            raise JobSourceValidationError("tenant key is required", path="tenantKey")
        tenant = next(
            (item for item in self.store.list_tenants(source_id) if item.tenant_key == key or item.id == key),
            None,
        )
        if tenant is None:
            raise JobSourceNotFoundError(key)
        return self.enqueue_crawl(tenant.id)

    def create_tenant(self, source_id: str, body: dict | None) -> dict:
        if source_id not in {"greenhouse", "lever"}:
            raise JobSourceNotFoundError(source_id)
        payload = body or {}
        if not isinstance(payload, dict):
            raise JobSourceValidationError("JSON object required")
        token = payload.get("boardToken") or payload.get("board_token") or payload.get("tenantKey") or payload.get(
            "tenant_key"
        )
        url = (
            payload.get("boardUrl")
            or payload.get("board_url")
            or payload.get("companyUrl")
            or payload.get("company_url")
        )
        company = payload.get("company")
        enabled = payload.get("enabled", True)
        if enabled is None:
            enabled = True
        if not isinstance(enabled, bool):
            raise JobSourceValidationError("enabled must be a boolean", path="enabled")
        tenant_key = parse_board_input(
            source_id,
            token=token if isinstance(token, str) else None,
            url=url if isinstance(url, str) else None,
        )
        config: dict[str, Any] = {"namespace": tenant_key}
        if source_id == "greenhouse":
            config["board_token"] = tenant_key
        else:
            config["site"] = tenant_key
        if isinstance(company, str) and company.strip():
            config["company"] = company.strip()
        existing = next(
            (item for item in self.store.list_tenants(source_id) if item.tenant_key == tenant_key),
            None,
        )
        if existing is not None:
            merged = dict(existing.config or {})
            merged.update(config)
            config = merged
        tenant = self.store.upsert_tenant(source_id, tenant_key, config=config, enabled=enabled)
        if self._preflight_listing(tenant):
            self._crawl_new_tenant(tenant)
        status_rows = self.source_status()
        row = next((item for item in status_rows if item["source"] == source_id), None)
        return {
            **tenant_payload(tenant),
            "status": row,
            "sources": status_rows,
        }

    def list_source_tenants(self, source_id: str) -> dict:
        if source_id not in {"greenhouse", "lever"}:
            raise JobSourceNotFoundError(source_id)
        tenants = self.store.list_tenants(source_id)
        return {"sourceId": source_id, "items": [tenant_payload(item) for item in tenants]}

    def delete_tenant(self, source_id: str, tenant_key: str) -> dict:
        if source_id not in {"greenhouse", "lever"}:
            raise JobSourceNotFoundError(source_id)
        key = (tenant_key or "").strip()
        if not key:
            raise JobSourceValidationError("tenant key is required", path="tenantKey")
        tenant = next(
            (item for item in self.store.list_tenants(source_id) if item.tenant_key == key or item.id == key),
            None,
        )
        if tenant is None:
            raise JobSourceNotFoundError(key)
        deleted = self.store.delete_tenant(tenant.id)
        status_rows = self.source_status()
        row = next((item for item in status_rows if item["source"] == source_id), None)
        return {
            **tenant_payload(deleted),
            "deleted": True,
            "status": row,
            "sources": status_rows,
        }

    def get_run(self, source_id: str, run_id: str) -> dict:
        run = self.store.get_run(run_id)
        if source_id in {"greenhouse", "lever"}:
            tenant = self.store.get_tenant(run.source_tenant_id)
            if tenant.source_id != source_id:
                raise JobSourceNotFoundError(run_id)
        elif run.source_tenant_id != source_id:
            raise JobSourceNotFoundError(run_id)
        return run_payload(run, tenant_id=run.source_tenant_id)

    def list_feed(
        self,
        *,
        sources: list[str] | None,
        q: str = "",
        location: str = "",
        status: str = "all",
        cursor: str | None = None,
        limit: int = 25,
        since: str | None = None,
    ) -> dict:
        limit = max(1, min(int(limit or 25), 100))
        cards = filter_cards(
            feed_cards(self.store),
            sources=sources,
            q=q,
            location=location,
            status=status,
            since=since,
        )
        start = 0
        if cursor:
            try:
                start = max(0, int(cursor))
            except ValueError:
                start = 0
        page = cards[start : start + limit]
        next_cursor = str(start + limit) if start + limit < len(cards) else None
        items = [{k: v for k, v in card.items() if k != "description"} for card in page]
        return {"items": items, "nextCursor": next_cursor, "total": len(cards)}

    def get_feed_job(self, job_id: str) -> dict:
        for card in feed_cards(self.store):
            if card["id"] == job_id:
                return card
        raise JobSourceNotFoundError(job_id)

    def source_status(self) -> list[dict]:
        rows = []
        for source_id in ("greenhouse", "lever"):
            tenants = self.store.list_tenants(source_id)
            if not tenants:
                rows.append(
                    {
                        "source": source_id,
                        "status": "unconfigured",
                        "lastSyncAt": None,
                        "backoffUntil": None,
                        "errorMessage": source_not_configured_message(source_id),
                        "progress": None,
                        "configured": False,
                        "tenantCount": 0,
                        "boards": [],
                    }
                )
                continue
            last_sync = None
            error = None
            progress = None
            backoff_until = None
            saw_syncing = False
            saw_error = False
            boards: list[dict] = []
            for tenant in tenants:
                board = self._board_status(tenant)
                boards.append(board)
                if board.get("backoffUntil") and (not backoff_until or board["backoffUntil"] > backoff_until):
                    backoff_until = board["backoffUntil"]
                if board.get("lastSyncAt") and (not last_sync or board["lastSyncAt"] > last_sync):
                    last_sync = board["lastSyncAt"]
                if board["status"] == "syncing":
                    saw_syncing = True
                    if board.get("progress"):
                        progress = board["progress"]
                elif board["status"] == "error":
                    saw_error = True
                    if board.get("errorMessage"):
                        error = board["errorMessage"]
            if saw_syncing:
                status = "syncing"
            elif backoff_until:
                status = "rate_limited"
            elif saw_error:
                status = "error"
            else:
                status = "ok"
            rows.append(
                {
                    "source": source_id,
                    "status": status,
                    "lastSyncAt": last_sync,
                    "backoffUntil": backoff_until,
                    "errorMessage": error,
                    "progress": progress,
                    "configured": True,
                    "tenantCount": len(tenants),
                    "boards": [{k: v for k, v in item.items() if k != "progress" and k != "backoffUntil"} for item in boards],
                }
            )
        return rows

    def _board_status(self, tenant: SourceTenant) -> dict:
        last_sync = None
        error = None
        progress = None
        backoff_until = None
        status = "ok"
        try:
            limit = self.store.get_rate_limit(tenant.id)
            if limit.backoff_until:
                backoff_until = limit.backoff_until
        except Exception:
            pass
        runs = self.store.list_runs(tenant.id)
        if runs:
            latest = runs[-1]
            last_sync = latest.finished_at or latest.updated_at
            if latest.status in {"running", "queued"}:
                status = "syncing"
                if latest.expected_count:
                    progress = f"{latest.completed_count}/{latest.expected_count}"
            elif latest.status in {"failed", "partial_success"}:
                status = "error"
                error = public_crawl_error(tenant.source_id, latest.error_summary, board=tenant.tenant_key)
            elif backoff_until:
                status = "rate_limited"
        elif backoff_until:
            status = "rate_limited"
        return {
            **_board_payload(tenant, status=status, error_message=error, last_sync_at=last_sync),
            "progress": progress,
            "backoffUntil": backoff_until,
        }

    def _preflight_listing(self, tenant: SourceTenant) -> bool:
        """Cheap public listing GET so a 404 token shows on the Settings board row.

        Returns True when the board looks reachable and is safe to crawl.
        Demo-seed tenants skip live HTTP. A preflight error is stamped and must
        not enqueue a second listing that would 404 again.
        """
        if (tenant.config or {}).get("demo_seed"):
            return False
        url = self._list_url(tenant, cursor=None, skip=0)
        assert_https_allowlisted(url, tenant.source_id)
        error: str | None = None
        try:
            response = self.fetcher.get(url, timeout=(3.0, 5.0))
            if response.status_code >= 400:
                error = str(response.status_code)
        except Exception as exc:
            error = str(exc)
        runs = self.store.list_runs(tenant.id)
        latest = runs[-1] if runs else None
        if error is None:
            if latest is not None and latest.status in {"failed", "partial_success"}:
                run = self.store.start_run(tenant.id, status="running")
                self.store.finish_run(run.id, status="succeeded")
            return True
        run = self.store.start_run(tenant.id, status="running")
        self.store.finish_run(
            run.id,
            status="failed",
            error_summary=public_crawl_error(tenant.source_id, error, board=tenant.tenant_key),
        )
        return False

    def _crawl_new_tenant(self, tenant: SourceTenant) -> None:
        """Enqueue this board immediately so Job Feed is not empty until Refresh."""
        if not tenant.enabled or (tenant.config or {}).get("demo_seed"):
            return
        try:
            self.enqueue_crawl(tenant.id)
            self.drain()
        except Exception:
            pass

    def schedule_due(self) -> list[dict]:
        cfg = get_app_settings()
        queued: list[dict] = []
        cap = max(1, int(getattr(cfg, "crawl_max_concurrent_per_tenant", 1) or 1))
        for schedule in self.store.due_schedules():
            try:
                tenant = self.store.get_tenant(schedule.source_tenant_id)
            except JobSourceNotFoundError:
                continue
            if not tenant.enabled:
                continue
            inflight = [
                item
                for item in self.store.list_runs(tenant.id)
                if item.status in {"queued", "running"}
            ]
            if len(inflight) >= cap:
                self.events.emit(
                    "rate_limited",
                    tenantId=tenant.id,
                    sourceId=tenant.source_id,
                    reason="per_tenant_cap",
                )
                continue
            run = self.store.start_run(tenant.id, status="queued")
            msg = {"tenantId": tenant.id, "runId": run.id}
            self.queue.enqueue(cfg.crawl_runs_queue, msg)
            queued.append(msg)
            self.events.emit("start", tenantId=tenant.id, sourceId=tenant.source_id, runId=run.id)
        return queued

    def process_crawl_run(self, payload: dict, *, dequeue_count: int = 1) -> SourceFetchRun:
        cfg = get_app_settings()
        tenant_id = payload["tenantId"]
        run_id = payload["runId"]
        if dequeue_count > cfg.crawl_poison_dequeue:
            self.events.emit("error", tenantId=tenant_id, runId=run_id, reason="poisoned")
            return self.store.finish_run(run_id, status="failed", error_summary="poisoned after repeated failures")
        tenant = self.store.get_tenant(tenant_id)
        self.events.emit("start", tenantId=tenant.id, sourceId=tenant.source_id, runId=run_id, board=tenant.tenant_key)
        if (tenant.config or {}).get("demo_seed"):
            finished = self.store.finish_run(run_id, status="succeeded")
            self.events.emit("finish", tenantId=tenant.id, sourceId=tenant.source_id, runId=run_id, status="succeeded")
            return finished
        self.store.set_run_status(run_id, "running")
        listing_ok = False
        listing_error: str | None = None
        seen_ids: list[str] = []
        try:
            seen_ids, listing_ok, listing_error = self._discover_jobs(tenant, run_id)
        except JobSourceRateLimitedError as exc:
            self.events.emit(
                "rate_limited",
                tenantId=tenant.id,
                sourceId=tenant.source_id,
                runId=run_id,
                board=tenant.tenant_key,
            )
            self.store.finish_run(
                run_id,
                status="failed",
                error_summary=public_crawl_error(tenant.source_id, str(exc), board=tenant.tenant_key),
            )
            return self.store.get_run(run_id)
        except JobSourceValidationError as exc:
            self.store.finish_run(
                run_id,
                status="failed",
                error_summary=public_crawl_error(tenant.source_id, str(exc), board=tenant.tenant_key),
            )
            return self.store.get_run(run_id)
        except Exception as exc:
            self.store.finish_run(
                run_id,
                status="failed",
                error_summary=public_crawl_error(tenant.source_id, str(exc), board=tenant.tenant_key),
            )
            return self.store.get_run(run_id)

        run = self.store.set_run_job_counts(run_id, expected=len(seen_ids))
        if listing_ok:
            self._deactivate_missing(tenant, run_id, set(seen_ids))
        if run.expected_count == 0:
            status = "succeeded" if listing_ok else "failed"
            existing = self.store.get_run(run_id).error_summary
            if listing_ok:
                summary = existing
            else:
                summary = public_crawl_error(
                    tenant.source_id,
                    listing_error or existing or "listing fetch failed",
                    board=tenant.tenant_key,
                )
            finished = self.store.finish_run(run_id, status=status, error_summary=summary)
            self.events.emit(
                "error" if status == "failed" else "finish",
                tenantId=tenant.id,
                sourceId=tenant.source_id,
                runId=run_id,
                status=status,
            )
            return finished
        return self.store.get_run(run_id)

    def process_job_fetch(self, payload: dict, *, dequeue_count: int = 1) -> SourceFetchRun:
        cfg = get_app_settings()
        tenant_id = payload["tenantId"]
        run_id = payload["runId"]
        if dequeue_count > cfg.crawl_poison_dequeue:
            run = self.store.set_run_job_counts(run_id, completed_delta=1)
            return self._maybe_finish(run, extra="poisoned job-fetch")
        tenant = self.store.get_tenant(tenant_id)
        try:
            self._fetch_and_ingest(tenant, run_id, payload)
        except JobSourceRateLimitedError as exc:
            self.store.record_request(
                tenant_id,
                run_id,
                endpoint=DETAIL_ENDPOINT,
                url=payload.get("detailUrl") or "",
                rate_limited=True,
                error=str(exc),
            )
        except Exception as exc:
            self.store.record_request(
                tenant_id,
                run_id,
                endpoint=DETAIL_ENDPOINT,
                url=payload.get("detailUrl") or "",
                error=str(exc),
            )
        run = self.store.set_run_job_counts(run_id, completed_delta=1)
        return self._maybe_finish(run)

    def drain(self) -> None:
        """Process any in-memory crawl-run and job-fetch messages (tests)."""
        cfg = get_app_settings()
        if not hasattr(self.queue, "pop_all"):
            return
        while True:
            runs = self.queue.pop_all(cfg.crawl_runs_queue)
            jobs = self.queue.pop_all(cfg.job_fetch_queue)
            if not runs and not jobs:
                break
            for payload in runs:
                self.process_crawl_run(payload)
            for payload in jobs:
                self.process_job_fetch(payload)

    def _maybe_finish(self, run: SourceFetchRun, extra: str | None = None) -> SourceFetchRun:
        if run.expected_count and run.completed_count >= run.expected_count:
            summary = extra
            if run.error_summary and extra:
                summary = f"{run.error_summary}; {extra}"
            elif run.error_summary:
                summary = run.error_summary
            finished = self.store.finish_run(run.id, status="succeeded", error_summary=summary)
            self.events.emit(
                "finish",
                tenantId=run.source_tenant_id,
                runId=run.id,
                status="succeeded",
            )
            self._rank_ingested_jobs(finished)
            return finished
        return run

    def _rank_ingested_jobs(self, run: SourceFetchRun) -> None:
        """Score newly crawled postings into Review so the queue is not empty until Rank."""
        try:
            tenant = self.store.get_tenant(run.source_tenant_id)
        except JobSourceNotFoundError:
            return
        if (tenant.config or {}).get("demo_seed"):
            return
        raws = {item.id: item for item in self.store.list_raw(tenant.id, current_only=True)}
        if not raws:
            return
        linked = {link.canonical_id for link in self.store.list_links() if link.raw_id in raws}
        cards = [card for card in feed_cards(self.store) if card["id"] in linked]
        if not cards:
            return
        try:
            from app.matching.runtime import get_service as get_matching
            from app.matching.runtime import try_get_service as try_matching
            from app.resumes.demo import DEMO_RESUME_ID, DEMO_USER
            from app.resumes.runtime import get_service as get_resume
            from app.resumes.runtime import try_get_service as try_resume
        except Exception:
            return
        matching = try_matching() or get_matching()
        resumes = try_resume() or get_resume()
        try:
            resume = resumes.get(DEMO_USER, DEMO_RESUME_ID)
        except Exception:
            return
        resume_text = _resume_rank_text(resume)
        if not resume_text.strip():
            return
        cfg = get_app_settings()
        job_ids = [card["id"] for card in cards][: cfg.match_max_rank_pairs]
        job_texts = [
            (card.get("description") or card.get("snippet") or card.get("title") or "").strip() or card["id"]
            for card in cards
        ][: cfg.match_max_rank_pairs]
        try:
            matching.rank(
                DEMO_USER,
                {
                    "resumeId": resume.id,
                    "resumeText": resume_text,
                    "jobIds": job_ids,
                    "jobTexts": job_texts,
                },
            )
            if hasattr(matching, "drain"):
                matching.drain()
        except Exception:
            return

    def _resolve_tenants(self, source_id: str) -> list[SourceTenant]:
        if source_id in {"greenhouse", "lever"}:
            return [item for item in self.store.list_tenants(source_id) if item.enabled]
        return [self.store.get_tenant(source_id)]

    def _discover_jobs(self, tenant: SourceTenant, run_id: str) -> tuple[list[str], bool, str | None]:
        cfg = get_app_settings()
        source_id = tenant.source_id
        seen_ids: list[str] = []
        seen_cursors: set[str] = set()
        listing_ok = False
        listing_error: str | None = None
        cursor_row = self.store.get_cursor(tenant.id, LIST_ENDPOINT)
        saved_cursor = cursor_row.cursor if cursor_row else None
        cursor = saved_cursor
        reset_once = False
        page_index = 0
        skip = 0
        while page_index < MAX_PAGES:
            page_index += 1
            url = self._list_url(tenant, cursor=cursor, skip=skip)
            token = cursor or str(skip)
            if token in seen_cursors:
                break
            if token:
                seen_cursors.add(token)
            response, error = self._get(tenant, run_id, url, endpoint=LIST_ENDPOINT)
            if response is None:
                listing_error = error
                if saved_cursor and cursor == saved_cursor and not reset_once and error == "404":
                    self.store.reset_cursor(tenant.id, LIST_ENDPOINT, run_id=run_id)
                    cursor = None
                    skip = 0
                    reset_once = True
                    continue
                if error == "404":
                    self.store.save_cursor(tenant.id, LIST_ENDPOINT, None)
                break
            listing_ok = True
            try:
                payload = json.loads(response.text() or "null")
            except json.JSONDecodeError:
                self.store.record_request(
                    tenant.id, run_id, endpoint=LIST_ENDPOINT, url=url, error="invalid json", status_code=response.status_code
                )
                break
            jobs, next_hint = self._parse_list(source_id, payload)
            if not jobs:
                self.store.save_cursor(tenant.id, LIST_ENDPOINT, None)
                break
            for job in jobs:
                parsed = greenhouse_job(job) if source_id == "greenhouse" else lever_job(job)
                job_id = parsed["source_posting_id"]
                if not job_id or job_id in seen_ids:
                    continue
                if not self._passes_filters(tenant, parsed, job):
                    continue
                seen_ids.append(job_id)
                detail_url = self._detail_url(tenant, job_id)
                self.queue.enqueue(
                    cfg.job_fetch_queue,
                    {
                        "tenantId": tenant.id,
                        "runId": run_id,
                        "sourcePostingId": job_id,
                        "detailUrl": detail_url,
                        "source": source_id,
                        "listJob": job,
                    },
                )
            if source_id == "greenhouse":
                next_cursor = next_hint
                if not next_cursor or next_cursor in seen_cursors:
                    self.store.save_cursor(tenant.id, LIST_ENDPOINT, None)
                    break
                self.store.save_cursor(tenant.id, LIST_ENDPOINT, next_cursor)
                cursor = next_cursor
            else:
                skip += len(jobs)
                if not next_hint:
                    self.store.save_cursor(tenant.id, LIST_ENDPOINT, None)
                    break
                self.store.save_cursor(tenant.id, LIST_ENDPOINT, str(skip))
                cursor = str(skip)
        return seen_ids, listing_ok, listing_error

    def _fetch_and_ingest(self, tenant: SourceTenant, run_id: str, payload: dict) -> None:
        source_id = tenant.source_id
        detail_url = payload.get("detailUrl") or self._detail_url(tenant, payload["sourcePostingId"])
        assert_https_allowlisted(detail_url, source_id)
        response, error = self._get(tenant, run_id, detail_url, endpoint=DETAIL_ENDPOINT)
        body_obj: Any
        if response is None:
            listed = payload.get("listJob")
            if not listed:
                raise JobSourceValidationError(error or "detail fetch failed", path="detail")
            body_obj = listed
            raw_text = payload_dumps(listed)
        else:
            try:
                body_obj = json.loads(response.text() or "null")
            except json.JSONDecodeError as exc:
                raise JobSourceValidationError("invalid detail json", path="detail") from exc
            raw_text = response.text()
        parsed = greenhouse_job(body_obj) if source_id == "greenhouse" else lever_job(body_obj)
        company = parsed["company"] or tenant.config.get("company") or tenant.tenant_key
        if not parsed["title"] or not company or not parsed["apply_url"]:
            self.store.record_request(
                tenant.id,
                run_id,
                endpoint=DETAIL_ENDPOINT,
                url=detail_url,
                status_code=400,
                error="missing title, company, or apply_url",
            )
            return
        blob_path = f"raw/{source_id}/{tenant.id}/{parsed['source_posting_id']}.json"
        blob_url = self.blobs.put(blob_path, raw_text.encode("utf-8"))
        namespace = str(tenant.config.get("namespace") or tenant.tenant_key)
        self.store.ingest_raw(
            tenant.id,
            source_posting_id=parsed["source_posting_id"],
            title=parsed["title"],
            location=parsed["location"],
            employment_type=parsed["employment_type"],
            company=company,
            apply_url=parsed["apply_url"],
            body=parsed["body"],
            payload=raw_text,
            listing_state="open",
            content_blob_url=blob_url,
            namespace=namespace,
            run_id=run_id,
        )

    def _get(
        self, tenant: SourceTenant, run_id: str, url: str, *, endpoint: str
    ) -> tuple[FetchResponse | None, str | None]:
        assert_https_allowlisted(url, tenant.source_id)
        retries = 0
        last_error = "request failed"
        backoff_ms = 0
        rate_limited = False
        while retries <= MAX_GET_RETRIES_TRANSIENT:
            try:
                self.store.consume_rate_limit(tenant.id)
            except JobSourceRateLimitedError as exc:
                until = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
                self.store.set_backoff(tenant.id, until=until)
                self.store.record_request(
                    tenant.id,
                    run_id,
                    endpoint=endpoint,
                    url=url,
                    rate_limited=True,
                    retry_count=retries,
                    error=str(exc),
                )
                raise
            try:
                response = self.fetcher.get(url, timeout=(10.0, 20.0))
            except Exception as exc:
                last_error = str(exc)
                retries += 1
                if retries > MAX_GET_RETRIES_NETWORK:
                    self.store.record_request(
                        tenant.id,
                        run_id,
                        endpoint=endpoint,
                        url=url,
                        retry_count=retries,
                        error=last_error,
                    )
                    return None, last_error
                delay = min(60.0, (2 ** (retries - 1)))
                self.sleeper(delay)
                continue
            if response.status_code in RETRYABLE_STATUS:
                rate_limited = response.status_code == 429
                retries += 1
                delay = self._retry_delay(response, retries)
                backoff_ms = int(delay * 1000)
                if retries > MAX_GET_RETRIES_TRANSIENT:
                    if rate_limited:
                        until = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat().replace(
                            "+00:00", "Z"
                        )
                        self.store.set_backoff(tenant.id, until=until)
                    self.store.record_request(
                        tenant.id,
                        run_id,
                        endpoint=endpoint,
                        url=url,
                        status_code=response.status_code,
                        retry_count=retries,
                        backoff_ms=backoff_ms,
                        rate_limited=rate_limited,
                        error=f"HTTP {response.status_code}",
                    )
                    return None, str(response.status_code)
                self.sleeper(delay)
                continue
            if response.status_code == 404:
                self.store.record_request(
                    tenant.id,
                    run_id,
                    endpoint=endpoint,
                    url=url,
                    status_code=404,
                    retry_count=retries,
                    error="not found",
                )
                return None, "404"
            if response.status_code >= 400:
                self.store.record_request(
                    tenant.id,
                    run_id,
                    endpoint=endpoint,
                    url=url,
                    status_code=response.status_code,
                    retry_count=retries,
                    error=f"HTTP {response.status_code}",
                )
                return None, str(response.status_code)
            self.store.record_request(
                tenant.id,
                run_id,
                endpoint=endpoint,
                url=url,
                status_code=response.status_code,
                retry_count=retries,
                backoff_ms=backoff_ms,
                rate_limited=rate_limited,
            )
            return response, None
        self.store.record_request(
            tenant.id, run_id, endpoint=endpoint, url=url, retry_count=retries, error=last_error, rate_limited=rate_limited
        )
        return None, last_error

    def _retry_delay(self, response: FetchResponse, attempt: int) -> float:
        header = response.header("Retry-After")
        if header:
            try:
                return min(60.0, max(0.0, float(header)))
            except ValueError:
                try:
                    when = parsedate_to_datetime(header)
                    delay = (when - datetime.now(timezone.utc)).total_seconds()
                    return min(60.0, max(0.0, delay))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(60.0, float(2 ** (attempt - 1)))

    def _list_url(self, tenant: SourceTenant, *, cursor: str | None, skip: int) -> str:
        base = tenant.config.get("base_url")
        if base:
            url = assert_https_allowlisted(str(base), tenant.source_id)
            if tenant.source_id == "greenhouse":
                page = int(cursor) if cursor and cursor.isdigit() else 1
                return with_query(url, page=page if page > 1 else None)
            return with_query(url, mode="json", skip=skip, limit=100)
        if tenant.source_id == "greenhouse":
            page = int(cursor) if cursor and cursor.isdigit() else 1
            return greenhouse_list_url(tenant.tenant_key, page=page if page > 1 else None)
        return lever_list_url(tenant.tenant_key, skip=skip)

    def _detail_url(self, tenant: SourceTenant, job_id: str) -> str:
        if tenant.source_id == "greenhouse":
            return greenhouse_detail_url(tenant.tenant_key, job_id)
        return lever_detail_url(tenant.tenant_key, job_id)

    def _parse_list(self, source_id: str, payload: Any) -> tuple[list[dict], str | None]:
        if source_id == "greenhouse":
            return greenhouse_list_jobs(payload)
        return lever_list_jobs(payload)

    def _passes_filters(self, tenant: SourceTenant, parsed: dict, raw_job: dict) -> bool:
        filters = tenant.config.get("filters") or {}
        if not isinstance(filters, dict):
            return True
        department = (filters.get("department") or filters.get("team") or "").strip().lower()
        location = (filters.get("location") or "").strip().lower()
        if department and department not in (parsed.get("department") or "").lower():
            return False
        if location and location not in (parsed.get("location") or "").lower():
            return False
        return True

    def _deactivate_missing(self, tenant: SourceTenant, run_id: str, seen_ids: set[str]) -> None:
        previous = [
            item
            for item in self.store.list_runs(tenant.id)
            if item.id != run_id and item.status in {"succeeded", "partial_success"} and item.finished_at
        ]
        previous.sort(key=lambda item: item.finished_at or "")
        if not previous:
            return
        last = previous[-1]
        cutoff = last.started_at or last.created_at
        for raw in self.store.list_raw(tenant.id, current_only=True):
            if raw.source_posting_id in seen_ids:
                continue
            if parse_ts(raw.seen_last_at) < parse_ts(cutoff):
                self.store.close_posting(tenant.id, raw.source_posting_id)
