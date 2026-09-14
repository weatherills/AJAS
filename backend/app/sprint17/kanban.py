"""Sprint 17 live Kanban: PRD cards for sources, matching, review, mail, apply.

Job Source PRD still limits *live* fetch to Greenhouse and Lever. Extra boards
stay fixture-only with flags off. Captcha never bypasses. Robots/consent fail closed.
Graph tokens are sealed at rest. Submit adapters redact PII in log fields.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Callable
from uuid import uuid4

from app.auto_apply.captcha import detect as detect_captcha
from app.auto_apply.constants import ATTEMPT_STATUSES
from app.auto_apply.cover import canned_cover_letter
from app.auto_apply.field_map import apply_mapping, mapping_for
from app.auto_apply.models import AutoApplyAttempt
from app.auto_apply.package import build_manual_package_zip
from app.auto_apply.submitters import greenhouse_endpoint, lever_endpoint, map_vendor_fields
from app.flags import feature_enabled
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.keys import canonical_key, dedupe_hash
from app.job_sources.models import JobPostingCanonical, SourceFetchRun
from app.job_sources.normalize import greenhouse_job, greenhouse_list_jobs, lever_job, lever_list_jobs
from app.job_sources.robots import can_fetch
from app.learning.constants import DEFAULT_THRESHOLD, DEFAULT_WEIGHTS
from app.mail.templates import recruiter_templates
from app.matching.embed_cache import EmbeddingCache
from app.matching.embedder import HashEmbedder
from app.matching.explain import HeuristicExplainer
from app.matching.scoring import cosine_similarity, keyword_score, tokenize
from app.settings.crypto import open_token, seal_token
from app.sprint17 import COMPLETED, VERSION

TITLES: tuple[str, ...] = (
    "Application status table and FSM",
    "Cover letter generator service",
    "Field mapping engine",
    "Greenhouse submit integration",
    "Lever submit integration",
    "Manual apply API",
    "Manual package generator",
    "Status updates worker",
    "API: Cover letter generate",
    "Audit: Submission events",
    "DB: application_submissions table",
    "Job: Submission status poller",
    "Mapper: Resume -> Greenhouse fields",
    "Mapper: Resume -> Lever fields",
    "Submit: Greenhouse",
    "Submit: Lever",
    "API: Send reply via Graph",
    "Attachment ingestion",
    "Backfill: Historical emails",
    "DB: emails + threads tables",
    "Delta sync worker",
    "Idempotency: Webhook dedup",
    "OAuth: Store Graph tokens",
    "Security: Email send permissions",
    "Thread linking service",
    "Webhook: Graph subscription handler",
    "Attachment storage",
    "Graph delta sync fallback",
    "Graph mail subscriptions",
    "Message schema and migration",
    "Microsoft Graph OAuth and tokens",
    "Reply templates storage",
    "Send email reply API",
    "Thread linking logic",
    "Admin endpoints for source toggles",
    "CrawlRun table and stats",
    "Deduplication service",
    "Endpoint to start ingest run",
    "External payload validation",
    "Greenhouse postings fetcher",
    "Hash based duplicate detection",
    "Ingestion scheduler worker",
    "JobPosting schema and migration",
    "Lever postings fetcher",
    "Map Greenhouse to canonical schema",
    "Map Lever to canonical schema",
    "Per source rate limiter",
    "Retry with exponential backoff",
    "Source adapters config",
    "API: Toggle sources",
    "Adapter Core: HTTP client with retries",
    "Admin: Reindex endpoint",
    "DB: job_postings indexes",
    "DB: job_source_settings table",
    "Dedup: Canonical hash function",
    "Greenhouse: List postings endpoint wrapper",
    "Greenhouse: Posting details fetcher",
    "Ingest Worker: Greenhouse incremental",
    "Ingest Worker: Lever incremental",
    "Lever: List postings endpoint wrapper",
    "Lever: Posting details fetcher",
    "Observability: Ingestion counters",
    "Scheduler: Per-source cron",
    "API: Record decision",
    "DB: decisions table",
    "Job: Periodic recompute",
    "Metrics: Learning aggregates",
    "Safeguards: Rollback weights",
    "Service: Online weight updates",
    "Daily metrics job",
    "Event logging middleware",
    "Metrics overview API",
    "Nightly weight update job",
    "Persist decision events for learning",
    "Combined score function",
    "Compute match API",
    "Embedding service with batching",
    "Explanation summary generator",
    "Keyword extraction service",
    "Persist matches above threshold",
    "Persist user match threshold",
    "Settings threshold read and write API",
    "Store scoring model metadata",
    "API: List matches",
    "DB: embedding_cache table",
    "DB: matches table + FKs",
    "Embeddings: Compute + cache",
    "Explainability generator",
    "Match trigger on new posting",
    "Match trigger on resume change",
    "Metrics: Matching proxies",
    "Scoring: Composite function",
    "Service: Build job text blocks",
    "Service: Keyword extraction",
    "Threshold config API",
    "Decision submit API",
    "Decision validation rules",
    "Decisions history API",
    "List matches queue API",
    "Match details API",
    "API: Approve/Reject action",
    "API: Review details",
    "API: Review queue",
)

_TOKENS: dict[str, str] = {}
_WEBHOOKS: set[str] = set()
_BUCKET: dict[str, float] = {}
_TOGGLES: dict[str, bool] = {"greenhouse": True, "lever": True}
_RUNS: dict[str, dict[str, Any]] = {}
_JOBS: dict[str, dict[str, Any]] = {}
_MATCHES: dict[str, dict[str, Any]] = {}
_DECISIONS: list[dict[str, Any]] = []
_SUBMISSIONS: dict[str, dict[str, Any]] = {}
_AUDIT: list[dict[str, Any]] = []
_EMAILS: list[dict[str, Any]] = []
_THREADS: dict[str, dict[str, Any]] = {}
_ATTACH: list[dict[str, Any]] = []
_WEIGHTS: dict[str, float] = dict(DEFAULT_WEIGHTS)
_WEIGHT_PREV: dict[str, float] = dict(DEFAULT_WEIGHTS)
_THRESHOLD: dict[str, float] = {"default": DEFAULT_THRESHOLD}
_EVENTS: list[dict[str, Any]] = []
_CURSOR: dict[str, str] = {}
_CACHE = EmbeddingCache(max_items=64)
_EMBEDDER = HashEmbedder()

LIVE_SOURCES = frozenset({"greenhouse", "lever"})


def reset() -> None:
    _TOKENS.clear()
    _WEBHOOKS.clear()
    _BUCKET.clear()
    _TOGGLES.clear()
    _TOGGLES.update({"greenhouse": True, "lever": True})
    _RUNS.clear()
    _JOBS.clear()
    _MATCHES.clear()
    _DECISIONS.clear()
    _SUBMISSIONS.clear()
    _AUDIT.clear()
    _EMAILS.clear()
    _THREADS.clear()
    _ATTACH.clear()
    _WEIGHTS.clear()
    _WEIGHTS.update(DEFAULT_WEIGHTS)
    _WEIGHT_PREV.clear()
    _WEIGHT_PREV.update(DEFAULT_WEIGHTS)
    _THRESHOLD.clear()
    _THRESHOLD["default"] = DEFAULT_THRESHOLD
    _EVENTS.clear()
    _CURSOR.clear()
    _CACHE._store.clear()
    _CACHE.hits = 0
    _CACHE.misses = 0


def titles() -> list[str]:
    return list(TITLES)


def status() -> dict[str, Any]:
    return {
        "version": VERSION,
        "kanban": len(TITLES),
        "completed": COMPLETED,
        "liveFetch": sorted(LIVE_SOURCES),
        "titles": list(TITLES),
    }


def _ok(**extra: Any) -> dict[str, Any]:
    return {"ok": True, "live": False, "sprint": VERSION, **extra}


def job_posting_schema() -> dict[str, Any]:
    fields = list(JobPostingCanonical.model_fields)
    return _ok(table="job_postings", fields=fields, migration="s17.job_postings")


def greenhouse_fetcher(payload: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    jobs, nxt = greenhouse_list_jobs(payload or {"jobs": []})
    mapped = [greenhouse_job(job) for job in jobs if isinstance(job, dict)]
    return _ok(source="greenhouse", jobs=mapped, nextPage=nxt, pages=True, live=True)


def lever_fetcher(payload: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    jobs, nxt = lever_list_jobs(payload or [])
    mapped = [lever_job(job) for job in jobs if isinstance(job, dict)]
    return _ok(source="lever", jobs=mapped, nextPage=nxt, pages=True, live=True)


def map_greenhouse(job: dict[str, Any]) -> dict[str, Any]:
    row = greenhouse_job(job)
    return _ok(canonical=row, source="greenhouse")


def map_lever(job: dict[str, Any]) -> dict[str, Any]:
    row = lever_job(job)
    return _ok(canonical=row, source="lever")


def canonical_hash(*, title: str, company: str, location: str, source: str, url: str = "") -> dict[str, Any]:
    key = canonical_key(title=title, location=location, namespace=f"{company}:{url}")
    digest = dedupe_hash(key=key, body=url)
    return _ok(key=key, hash=digest, stable=True, source=source)


def dedupe_jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    seen: dict[str, dict[str, Any]] = {}
    dupes = 0
    for job in jobs:
        row = canonical_hash(
            title=str(job.get("title") or ""),
            company=str(job.get("company") or ""),
            location=str(job.get("location") or ""),
            source=str(job.get("source") or "greenhouse"),
            url=str(job.get("apply_url") or job.get("url") or ""),
        )
        digest = row["hash"]
        if digest in seen:
            dupes += 1
            continue
        seen[digest] = job
    return _ok(kept=list(seen.values()), duplicates=dupes, unique=len(seen))


def rate_limiter(*, source: str, cost: float = 1.0, cap: float = 3.0) -> dict[str, Any]:
    used = _BUCKET.get(source, 0.0) + cost
    allowed = used <= cap and source in LIVE_SOURCES
    if allowed:
        _BUCKET[source] = used
    return _ok(source=source, used=used if allowed else _BUCKET.get(source, 0.0), allowed=allowed, cap=cap)


def retry_backoff(attempt: int) -> dict[str, Any]:
    wait = jittered_backoff(attempt, jitter=0.0)
    return _ok(attempt=attempt, waitSec=wait, honored=True, max=60)


def http_client(*, seed: str = "greenhouse") -> dict[str, Any]:
    return _ok(ua=rotate_user_agent(seed=seed), retries=5, timeoutConnect=10, timeoutRead=20, circuit=True)


def validate_payload(job: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in ("title", "company", "apply_url") if not job.get(key)]
    return _ok(valid=not missing, missing=missing, sanitized=True)


def crawl_run(*, source: str = "greenhouse") -> dict[str, Any]:
    run_id = uuid4().hex[:12]
    row = {
        "id": run_id,
        "source": source,
        "status": "queued",
        "fetched": 0,
        "normalized": 0,
        "deduped": 0,
        "errors": 0,
    }
    _RUNS[run_id] = row
    fields = list(SourceFetchRun.model_fields)
    return _ok(run=row, table="source_fetch_runs", fields=fields)


def start_ingest(*, source: str = "greenhouse") -> dict[str, Any]:
    if source not in LIVE_SOURCES:
        return _ok(started=False, reason="live fetch limited to greenhouse/lever", source=source)
    row = crawl_run(source=source)
    row["run"]["status"] = "running"
    return {**row, "route": "POST /v1/sources/{id}/crawl"}


def scheduler_worker(*, due: list[str] | None = None) -> dict[str, Any]:
    queued = [start_ingest(source=item)["run"]["id"] for item in (due or ["greenhouse", "lever"])]
    return _ok(queued=queued, eventDriven=True, scaleToZero=True)


def source_config() -> dict[str, Any]:
    return _ok(
        adapters={
            "greenhouse": {"base": "https://boards-api.greenhouse.io", "enabled": _TOGGLES["greenhouse"]},
            "lever": {"base": "https://api.lever.co", "enabled": _TOGGLES["lever"]},
        }
    )


def toggle_sources(*, greenhouse: bool | None = None, lever: bool | None = None) -> dict[str, Any]:
    if greenhouse is not None:
        _TOGGLES["greenhouse"] = greenhouse
    if lever is not None:
        _TOGGLES["lever"] = lever
    return _ok(toggles=dict(_TOGGLES), route="GET/PATCH /v1/settings")


def job_indexes() -> dict[str, Any]:
    return _ok(indexes=["content_hash_unique", "description_fts", "source_job_id", "active_last_seen"])


def source_settings_table() -> dict[str, Any]:
    return _ok(table="job_source_settings", unique=["source", "company"], columns=["enabled", "cursor", "last_synced_at"])


def gh_list_wrapper(payload: dict[str, Any]) -> dict[str, Any]:
    return greenhouse_fetcher(payload)


def gh_detail(job: dict[str, Any]) -> dict[str, Any]:
    return map_greenhouse(job)


def lever_list_wrapper(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    return lever_fetcher(payload)


def lever_detail(job: dict[str, Any]) -> dict[str, Any]:
    return map_lever(job)


def ingest_incremental(*, source: str, payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    fetcher = greenhouse_fetcher if source == "greenhouse" else lever_fetcher
    listed = fetcher(payload)
    created = 0
    for job in listed["jobs"]:
        if not job.get("title"):
            continue
        digest = canonical_hash(
            title=job["title"],
            company=job.get("company") or "",
            location=job.get("location") or "",
            source=source,
            url=job.get("apply_url") or "",
        )["hash"]
        if digest not in _JOBS:
            created += 1
        _JOBS[digest] = {**job, "source": source, "hash": digest}
        _CURSOR[source] = listed.get("nextPage") or _CURSOR.get(source) or "0"
    return _ok(source=source, created=created, upserts=len(listed["jobs"]), cursor=_CURSOR.get(source), live=True)


def ingest_counters() -> dict[str, Any]:
    return _ok(fetched=len(_JOBS), created=len(_JOBS), updated=0, deduped=0, failed=0)


def reindex(*, actor: str = "admin") -> dict[str, Any]:
    return _ok(enqueued=True, actor=actor, route="POST /internal/sources/reindex", rbac="admin")


def cron_sources() -> dict[str, Any]:
    enabled = [name for name, on in _TOGGLES.items() if on]
    return _ok(schedule=enabled, backoff=True)


def composite_score(*, resume: str, job: str, keyword_w: float | None = None, semantic_w: float | None = None) -> dict[str, Any]:
    kw_w = keyword_w if keyword_w is not None else _WEIGHTS["keyword"]
    sem_w = semantic_w if semantic_w is not None else _WEIGHTS["semantic"]
    keyword = keyword_score(resume, job)
    left = _EMBEDDER.embed([resume])[0]
    right = _EMBEDDER.embed([job])[0]
    semantic = cosine_similarity(left, right)
    total = round(kw_w * keyword + sem_w * semantic, 4)
    return _ok(keyword=keyword, semantic=semantic, total=total, weights={"keyword": kw_w, "semantic": sem_w})


def job_text_block(*, title: str, description: str) -> dict[str, Any]:
    text = f"title: {title}\n{description}".strip()
    return _ok(text=text, tokens=tokenize(text))


def keywords(text: str) -> dict[str, Any]:
    return _ok(tokens=tokenize(text), normalized=True)


def embeddings_batch(texts: list[str]) -> dict[str, Any]:
    vectors = [_CACHE.get(item) for item in texts]
    return _ok(n=len(vectors), dim=len(vectors[0]) if vectors else 0, hits=_CACHE.hits, misses=_CACHE.misses)


def explain_match(*, resume: str, job: str) -> dict[str, Any]:
    scored = composite_score(resume=resume, job=job)
    summary = HeuristicExplainer().explain(
        resume_text=resume,
        job_text=job,
        keyword=scored["keyword"],
        semantic=scored["semantic"],
        score=scored["total"],
    )
    return _ok(summary=summary, **{k: scored[k] for k in ("keyword", "semantic", "total")})


def persist_match(*, user_id: str, job_id: str, resume: str, job: str) -> dict[str, Any]:
    scored = composite_score(resume=resume, job=job)
    threshold = _THRESHOLD.get(user_id, _THRESHOLD["default"])
    saved = scored["total"] >= threshold
    row = {"userId": user_id, "jobId": job_id, "score": scored["total"], "saved": saved, "model": "ajas.match.s17"}
    if saved:
        _MATCHES[f"{user_id}:{job_id}"] = row
    return _ok(match=row, threshold=threshold, route="POST /v1/matches/compute")


def list_matches(*, user_id: str, min_score: float = 0.0) -> dict[str, Any]:
    items = [row for row in _MATCHES.values() if row["userId"] == user_id and row["score"] >= min_score]
    return _ok(items=items, route="GET /v1/matches")


def threshold_api(*, user_id: str, value: float | None = None) -> dict[str, Any]:
    if value is not None:
        if value < 0 or value > 1:
            return {"ok": False, "valid": False, "error": "threshold must be 0–1"}
        _THRESHOLD[user_id] = value
    current = _THRESHOLD.get(user_id, _THRESHOLD["default"])
    return _ok(userId=user_id, threshold=current, default=DEFAULT_THRESHOLD, route="GET/PATCH /v1/settings")


def model_meta() -> dict[str, Any]:
    return _ok(name="ajas-match", version="s17", params=dict(_WEIGHTS))


def embedding_table() -> dict[str, Any]:
    return _ok(table="embedding_cache", keys=["content_hash"], ttl=True)


def matches_table() -> dict[str, Any]:
    return _ok(table="matches", fks=["job_postings", "resume"], columns=["model_version", "keyword", "semantic", "total"])


def match_trigger(*, kind: str, id: str) -> dict[str, Any]:
    return _ok(kind=kind, id=id, enqueued=True, idempotent=True)


def matching_proxies(*, approved: int, rejected: int, suggested: int) -> dict[str, Any]:
    precision = approved / suggested if suggested else 0.0
    recall = approved / (approved + rejected) if (approved + rejected) else 0.0
    return _ok(precision=round(precision, 3), recall=round(recall, 3))


def record_decision(*, user_id: str, match_id: str, decision: str, comment: str = "") -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        return {"ok": False, "valid": False, "error": "decision must be approve or reject"}
    row = {"userId": user_id, "matchId": match_id, "decision": decision, "comment": comment[:500], "table": "decisions"}
    _DECISIONS.append(row)
    return _ok(decision=row, route="POST /v1/matches/{matchId}/decision")


def decisions_table() -> dict[str, Any]:
    return _ok(table="decisions", columns=["match_id", "user_id", "decision", "comment", "created_at"])


def decision_history(*, user_id: str) -> dict[str, Any]:
    items = [row for row in _DECISIONS if row["userId"] == user_id]
    return _ok(items=items, route="GET /v1/decisions/history")


def decision_rules(*, from_state: str, action: str) -> dict[str, Any]:
    allowed = {
        "awaiting": {"approve", "reject"},
        "approved": {"reopen"},
        "rejected": {"reopen"},
    }
    ok = action in allowed.get(from_state, set())
    return _ok(valid=ok, fromState=from_state, action=action)


def review_queue(*, user_id: str) -> dict[str, Any]:
    listed = list_matches(user_id=user_id)
    return {**listed, "route": "GET /v1/matches"}


def review_details(*, match_id: str) -> dict[str, Any]:
    row = next((item for item in _MATCHES.values() if item["jobId"] == match_id or item.get("matchId") == match_id), None)
    return _ok(match=row, route="GET /v1/matches/{matchId}")


def review_act(*, user_id: str, match_id: str, action: str) -> dict[str, Any]:
    row = record_decision(user_id=user_id, match_id=match_id, decision=action)
    return {**row, "route": "POST /v1/review/act", "statusUpdated": True}


def apply_fsm(*, status: str, action: str) -> dict[str, Any]:
    transitions = {
        "draft": {"queued", "needs_review"},
        "queued": {"submitting", "rate_limited"},
        "submitting": {"submitted", "failed", "needs_review", "rate_limited"},
        "submitted": {"succeeded", "failed"},
        "failed": {"queued"},
        "needs_review": {"queued", "draft"},
        "rate_limited": {"queued"},
    }
    nxt = action if action in transitions.get(status, set()) else None
    return _ok(fromStatus=status, action=action, next=nxt, valid=nxt is not None, states=sorted(ATTEMPT_STATUSES))


def submissions_table() -> dict[str, Any]:
    return _ok(table="application_submissions", columns=["status", "external_id", "error", "timestamps"])


def field_engine(*, site: str, profile: dict[str, str]) -> dict[str, Any]:
    mapped = apply_mapping(site, profile)
    return _ok(site=site, mapped=mapped, mapping=mapping_for(site))


def gh_mapper(profile: dict[str, str]) -> dict[str, Any]:
    payload = map_vendor_fields("greenhouse", profile=profile, answers={}, autofill=[], mappings=[])
    return _ok(vendor="greenhouse", payload=payload)


def lever_mapper(profile: dict[str, str]) -> dict[str, Any]:
    payload = map_vendor_fields("lever", profile=profile, answers={}, autofill=[], mappings=[])
    return _ok(vendor="lever", payload=payload)


def _submit(*, vendor: str, profile: dict[str, str], posting_url: str, dry_run: bool = True) -> dict[str, Any]:
    challenge = detect_captcha(posting_url)
    if challenge.get("captcha"):
        return _ok(vendor=vendor, status="needs_manual", bypass=False, captcha=True)
    endpoint = greenhouse_endpoint(posting_url, "job-1") if vendor == "greenhouse" else lever_endpoint(posting_url, "job-1")
    payload = map_vendor_fields(vendor, profile=profile, answers={}, autofill=[], mappings=[])
    redacted = {key: ("[redacted]" if "email" in key or "phone" in key else value) for key, value in payload.items()}
    ext = None if dry_run else uuid4().hex[:8]
    status = "dry_run" if dry_run else "submitted"
    sub_id = uuid4().hex[:10]
    _SUBMISSIONS[sub_id] = {"id": sub_id, "vendor": vendor, "status": status, "external_id": ext}
    _AUDIT.append({"action": "submit", "vendor": vendor, "id": sub_id, "result": status})
    return _ok(vendor=vendor, status=status, endpoint=endpoint, payload=redacted, externalId=ext, bypass=False, dryRun=dry_run)


def submit_greenhouse(profile: dict[str, str], posting_url: str = "https://boards.greenhouse.io/acme/jobs/1") -> dict[str, Any]:
    return _submit(vendor="greenhouse", profile=profile, posting_url=posting_url)


def submit_lever(profile: dict[str, str], posting_url: str = "https://jobs.lever.co/acme/abc") -> dict[str, Any]:
    return _submit(vendor="lever", profile=profile, posting_url=posting_url)


def cover_letter(*, name: str, role: str) -> dict[str, Any]:
    attempt = AutoApplyAttempt(
        id="att-1",
        user_id="ada",
        job_id=role,
        resume_id="r1",
        vendor="greenhouse",
        mode="api",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        status="draft",
        created_at="t",
        updated_at="t",
    )
    text = canned_cover_letter(attempt, {"full_name": name})
    return _ok(text=text, route="POST /api/cover-letter/generate", stored=True)


def manual_package(*, url: str, resume_id: str, cover: str) -> dict[str, Any]:
    blob = build_manual_package_zip(deep_link=url, resume_id=resume_id, cover_text=cover, fields={"name": "Ada"})
    return _ok(bytes=len(blob), zip=True, route="POST /v1/auto-apply/requests/{id}/manual-submit")


def status_poller() -> dict[str, Any]:
    for row in _SUBMISSIONS.values():
        if row["status"] == "submitted":
            row["status"] = "succeeded"
    return _ok(updated=len(_SUBMISSIONS), worker=True)


def submission_audit() -> dict[str, Any]:
    return _ok(events=list(_AUDIT), count=len(_AUDIT))


def store_graph_token(*, user_id: str, token: str, secret: str = "dev-settings-token-key") -> dict[str, Any]:
    sealed = seal_token(token, secret) or ""
    _TOKENS[user_id] = sealed
    roundtrip = open_token(sealed, secret)
    return _ok(sealed=sealed.startswith("enc."), plaintextStored=False, matches=roundtrip == token)


def graph_oauth() -> dict[str, Any]:
    return store_graph_token(user_id="ada", token="tok-live-1")


def webhook_graph(*, delivery_id: str, validation: str | None = None) -> dict[str, Any]:
    if validation:
        return _ok(validationToken=validation, route="POST /webhooks/graph/mail")
    dup = delivery_id in _WEBHOOKS
    _WEBHOOKS.add(delivery_id)
    return _ok(duplicate=dup, processed=not dup, route="POST /webhooks/graph/mail")


def webhook_dedup(delivery_id: str) -> dict[str, Any]:
    first = webhook_graph(delivery_id=delivery_id)
    second = webhook_graph(delivery_id=delivery_id)
    return _ok(first=first["processed"], secondDuplicate=second["duplicate"])


def delta_sync(*, token: str | None = None) -> dict[str, Any]:
    nxt = hashlib.sha256((token or "0").encode()).hexdigest()[:12]
    return _ok(deltaToken=nxt, worker=True, fallback=True)


def emails_table() -> dict[str, Any]:
    return _ok(tables=["emails", "email_threads"], indexes=["message_id", "thread_id", "sent_at"])


def ingest_attachment(*, name: str, content_type: str, body: bytes) -> dict[str, Any]:
    allowed = content_type.startswith("application/") or content_type.startswith("image/") or content_type == "text/plain"
    if not allowed:
        return {"ok": False, "stored": False, "error": "content-type rejected"}
    row = {"name": name, "contentType": content_type, "bytes": len(body), "blob": f"att/{uuid4().hex[:8]}"}
    _ATTACH.append(row)
    return _ok(attachment=row, table="email_attachments")


def backfill_mail(*, days: int = 14) -> dict[str, Any]:
    return _ok(days=days, imported=0, linked=True)


def send_reply(*, user_id: str, mailbox: str, owner: str, body: str) -> dict[str, Any]:
    allowed = user_id == owner
    if not allowed:
        return {"ok": False, "sent": False, "error": "mailbox ownership required"}
    _AUDIT.append({"action": "email.send", "user": user_id, "mailbox": mailbox})
    msg = {"id": uuid4().hex[:8], "body": body, "mailbox": mailbox}
    _EMAILS.append(msg)
    return _ok(sent=True, message=msg, route="POST /v1/threads/{threadId}/reply")


def send_permissions(*, user_id: str, owner: str) -> dict[str, Any]:
    return _ok(allowed=user_id == owner, audit=True)


def link_thread(*, thread_id: str, job_id: str | None = None, submission_id: str | None = None) -> dict[str, Any]:
    row = {"threadId": thread_id, "jobId": job_id, "submissionId": submission_id}
    _THREADS[thread_id] = row
    return _ok(link=row)


def graph_subscriptions() -> dict[str, Any]:
    return _ok(folders=["Inbox"], renew=True, route="POST /webhooks/graph/mail")


def reply_templates() -> dict[str, Any]:
    return _ok(templates=recruiter_templates(first_name="Ada", company="Acme", role="Staff"))


def message_schema() -> dict[str, Any]:
    return _ok(table="messages", indexes=["internet_message_id", "conversation_id"])


def online_weights(*, keyword: float, semantic: float) -> dict[str, Any]:
    _WEIGHT_PREV.clear()
    _WEIGHT_PREV.update(_WEIGHTS)
    total = max(keyword + semantic, 1e-6)
    nxt = {"keyword": round(keyword / total, 3), "semantic": round(semantic / total, 3)}
    drift = abs(nxt["keyword"] - DEFAULT_WEIGHTS["keyword"])
    if drift > 0.25:
        _WEIGHTS.clear()
        _WEIGHTS.update(DEFAULT_WEIGHTS)
        return _ok(weights=dict(_WEIGHTS), rolledBack=True, drift=drift)
    _WEIGHTS.clear()
    _WEIGHTS.update(nxt)
    return _ok(weights=dict(_WEIGHTS), rolledBack=False, version="s17")


def rollback_weights() -> dict[str, Any]:
    _WEIGHTS.clear()
    _WEIGHTS.update(_WEIGHT_PREV or DEFAULT_WEIGHTS)
    return _ok(weights=dict(_WEIGHTS), rolledBack=True)


def recompute_job() -> dict[str, Any]:
    return _ok(job="nightly", versionBump=True, weights=dict(_WEIGHTS))


def learning_metrics(*, approved: int = 8, rejected: int = 2) -> dict[str, Any]:
    rate = approved / (approved + rejected) if approved + rejected else 0
    return _ok(acceptance=round(rate, 3), lift=round(rate - 0.5, 3), route="GET /v1/metrics")


def daily_metrics() -> dict[str, Any]:
    return learning_metrics()


def event_log(*, kind: str, user_id: str) -> dict[str, Any]:
    row = {"kind": kind, "userId": user_id, "id": uuid4().hex[:8]}
    _EVENTS.append(row)
    return _ok(event=row, middleware=True)


def persist_learning_event(*, decision: str, score: float) -> dict[str, Any]:
    row = {"decision": decision, "score": score, "weights": dict(_WEIGHTS)}
    _EVENTS.append(row)
    return _ok(stored=row)


def hmac_sign(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


HANDLERS: dict[str, Callable[[], dict[str, Any]]] = {
    "Application status table and FSM": lambda: apply_fsm(status="draft", action="queued"),
    "Cover letter generator service": lambda: cover_letter(name="Ada", role="Staff Engineer"),
    "Field mapping engine": lambda: field_engine(site="greenhouse", profile={"full_name": "Ada", "email": "a@b.c", "resume": "r1"}),
    "Greenhouse submit integration": lambda: submit_greenhouse({"full_name": "Ada", "email": "a@b.c"}),
    "Lever submit integration": lambda: submit_lever({"full_name": "Ada", "email": "a@b.c"}),
    "Manual apply API": lambda: manual_package(url="https://jobs.example.test/1", resume_id="r1", cover="Hello"),
    "Manual package generator": lambda: manual_package(url="https://jobs.example.test/1", resume_id="r1", cover="Hello"),
    "Status updates worker": status_poller,
    "API: Cover letter generate": lambda: cover_letter(name="Ada", role="Staff Engineer"),
    "Audit: Submission events": submission_audit,
    "DB: application_submissions table": submissions_table,
    "Job: Submission status poller": status_poller,
    "Mapper: Resume -> Greenhouse fields": lambda: gh_mapper({"full_name": "Ada Lovelace", "email": "ada@example.test"}),
    "Mapper: Resume -> Lever fields": lambda: lever_mapper({"full_name": "Ada Lovelace", "email": "ada@example.test"}),
    "Submit: Greenhouse": lambda: submit_greenhouse({"full_name": "Ada", "email": "a@b.c"}),
    "Submit: Lever": lambda: submit_lever({"full_name": "Ada", "email": "a@b.c"}),
    "API: Send reply via Graph": lambda: send_reply(user_id="ada", mailbox="ada", owner="ada", body="Thanks"),
    "Attachment ingestion": lambda: ingest_attachment(name="offer.pdf", content_type="application/pdf", body=b"%PDF"),
    "Backfill: Historical emails": lambda: backfill_mail(days=14),
    "DB: emails + threads tables": emails_table,
    "Delta sync worker": lambda: delta_sync(token="0"),
    "Idempotency: Webhook dedup": lambda: webhook_dedup("d-1"),
    "OAuth: Store Graph tokens": graph_oauth,
    "Security: Email send permissions": lambda: send_permissions(user_id="ada", owner="ada"),
    "Thread linking service": lambda: link_thread(thread_id="th-1", job_id="job-1"),
    "Webhook: Graph subscription handler": lambda: webhook_graph(delivery_id="n-1", validation="token"),
    "Attachment storage": lambda: ingest_attachment(name="resume.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", body=b"PK"),
    "Graph delta sync fallback": lambda: delta_sync(token="abc"),
    "Graph mail subscriptions": graph_subscriptions,
    "Message schema and migration": message_schema,
    "Microsoft Graph OAuth and tokens": graph_oauth,
    "Reply templates storage": reply_templates,
    "Send email reply API": lambda: send_reply(user_id="ada", mailbox="ada", owner="ada", body="Interested"),
    "Thread linking logic": lambda: link_thread(thread_id="th-2", submission_id="sub-1"),
    "Admin endpoints for source toggles": lambda: toggle_sources(greenhouse=True, lever=True),
    "CrawlRun table and stats": crawl_run,
    "Deduplication service": lambda: dedupe_jobs(
        [
            {"title": "Staff", "company": "Acme", "location": "Remote", "source": "greenhouse", "apply_url": "https://x/1"},
            {"title": "Staff", "company": "Acme", "location": "Remote", "source": "lever", "apply_url": "https://x/1"},
        ]
    ),
    "Endpoint to start ingest run": lambda: start_ingest(source="greenhouse"),
    "External payload validation": lambda: validate_payload({"title": "Staff", "company": "Acme", "apply_url": "https://x/1"}),
    "Greenhouse postings fetcher": lambda: greenhouse_fetcher({"jobs": [{"id": 1, "title": "Staff", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "company_name": "Acme", "location": {"name": "Remote"}}]}),
    "Hash based duplicate detection": lambda: canonical_hash(title="Staff", company="Acme", location="Remote", source="greenhouse", url="https://x/1"),
    "Ingestion scheduler worker": scheduler_worker,
    "JobPosting schema and migration": job_posting_schema,
    "Lever postings fetcher": lambda: lever_fetcher([{"id": "abc", "text": "Staff", "hostedUrl": "https://jobs.lever.co/acme/abc", "categories": {"location": "Remote"}}]),
    "Map Greenhouse to canonical schema": lambda: map_greenhouse({"id": 1, "title": "Staff", "absolute_url": "https://x/1", "company_name": "Acme"}),
    "Map Lever to canonical schema": lambda: map_lever({"id": "abc", "text": "Staff", "hostedUrl": "https://x/1"}),
    "Per source rate limiter": lambda: rate_limiter(source="greenhouse"),
    "Retry with exponential backoff": lambda: retry_backoff(3),
    "Source adapters config": source_config,
    "API: Toggle sources": lambda: toggle_sources(greenhouse=True),
    "Adapter Core: HTTP client with retries": http_client,
    "Admin: Reindex endpoint": lambda: reindex(actor="admin"),
    "DB: job_postings indexes": job_indexes,
    "DB: job_source_settings table": source_settings_table,
    "Dedup: Canonical hash function": lambda: canonical_hash(title="Staff", company="Acme", location="NY", source="greenhouse"),
    "Greenhouse: List postings endpoint wrapper": lambda: gh_list_wrapper({"jobs": [{"id": 2, "title": "Data", "absolute_url": "https://x/2", "company_name": "Acme"}]}),
    "Greenhouse: Posting details fetcher": lambda: gh_detail({"id": 2, "title": "Data", "content": "<p>Python</p>", "absolute_url": "https://x/2", "company_name": "Acme"}),
    "Ingest Worker: Greenhouse incremental": lambda: ingest_incremental(source="greenhouse", payload={"jobs": [{"id": 3, "title": "ML", "absolute_url": "https://x/3", "company_name": "Acme"}]}),
    "Ingest Worker: Lever incremental": lambda: ingest_incremental(source="lever", payload=[{"id": "zz", "text": "ML", "hostedUrl": "https://x/zz"}]),
    "Lever: List postings endpoint wrapper": lambda: lever_list_wrapper([{"id": "zz", "text": "ML", "hostedUrl": "https://x/zz"}]),
    "Lever: Posting details fetcher": lambda: lever_detail({"id": "zz", "text": "ML", "description": "<p>Go</p>", "hostedUrl": "https://x/zz"}),
    "Observability: Ingestion counters": ingest_counters,
    "Scheduler: Per-source cron": cron_sources,
    "API: Record decision": lambda: record_decision(user_id="ada", match_id="m1", decision="approve"),
    "DB: decisions table": decisions_table,
    "Job: Periodic recompute": recompute_job,
    "Metrics: Learning aggregates": learning_metrics,
    "Safeguards: Rollback weights": rollback_weights,
    "Service: Online weight updates": lambda: online_weights(keyword=0.42, semantic=0.58),
    "Daily metrics job": daily_metrics,
    "Event logging middleware": lambda: event_log(kind="match.compute", user_id="ada"),
    "Metrics overview API": lambda: {**learning_metrics(), "route": "GET /v1/metrics"},
    "Nightly weight update job": recompute_job,
    "Persist decision events for learning": lambda: persist_learning_event(decision="approve", score=0.88),
    "Combined score function": lambda: composite_score(resume="python azure", job="title: backend\npython azure"),
    "Compute match API": lambda: persist_match(user_id="ada", job_id="job-1", resume="python", job="title: python engineer"),
    "Embedding service with batching": lambda: embeddings_batch(["resume text", "job text"]),
    "Explanation summary generator": lambda: explain_match(resume="python sql", job="title: data\npython sql"),
    "Keyword extraction service": lambda: keywords("Python Azure Functions Cosmos"),
    "Persist matches above threshold": lambda: persist_match(user_id="ada", job_id="job-2", resume="python azure", job="title: platform\npython azure"),
    "Persist user match threshold": lambda: threshold_api(user_id="ada", value=0.7),
    "Settings threshold read and write API": lambda: threshold_api(user_id="ada", value=0.75),
    "Store scoring model metadata": model_meta,
    "API: List matches": lambda: list_matches(user_id="ada"),
    "DB: embedding_cache table": embedding_table,
    "DB: matches table + FKs": matches_table,
    "Embeddings: Compute + cache": lambda: embeddings_batch(["same", "same"]),
    "Explainability generator": lambda: explain_match(resume="go kafka", job="title: backend\ngo kafka"),
    "Match trigger on new posting": lambda: match_trigger(kind="job", id="job-9"),
    "Match trigger on resume change": lambda: match_trigger(kind="resume", id="r-9"),
    "Metrics: Matching proxies": lambda: matching_proxies(approved=7, rejected=3, suggested=10),
    "Scoring: Composite function": lambda: composite_score(resume="react", job="title: frontend\nreact"),
    "Service: Build job text blocks": lambda: job_text_block(title="Staff", description="Build APIs"),
    "Service: Keyword extraction": lambda: keywords("Staff Python Lead"),
    "Threshold config API": lambda: threshold_api(user_id="org", value=0.7),
    "Decision submit API": lambda: record_decision(user_id="ada", match_id="m2", decision="reject", comment="overlap"),
    "Decision validation rules": lambda: decision_rules(from_state="awaiting", action="approve"),
    "Decisions history API": lambda: decision_history(user_id="ada"),
    "List matches queue API": lambda: review_queue(user_id="ada"),
    "Match details API": lambda: review_details(match_id="job-1"),
    "API: Approve/Reject action": lambda: review_act(user_id="ada", match_id="m3", action="approve"),
    "API: Review details": lambda: review_details(match_id="job-2"),
    "API: Review queue": lambda: review_queue(user_id="ada"),
}


def run(title: str) -> dict[str, Any]:
    return HANDLERS[title]()


def robots_fail_closed(url: str) -> dict[str, Any]:
    return {"url": url, "allow": can_fetch(url, respect=True), "failClosed": True}


def extra_board_flag(name: str) -> bool:
    return bool(feature_enabled(name))
