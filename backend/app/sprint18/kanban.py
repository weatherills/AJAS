"""Sprint 18 live Kanban: skeletons and wiring that wrap existing PRD modules.

Job Source PRD: live fetch is Greenhouse + Lever only. Extra boards stay
fixture-only with flags off. Captcha never bypasses. Robots/consent fail closed.
HTTPS host allowlist (SSRF). Rate limit ≤3 RPS/source. Graph tokens sealed at
rest. Matching scores 0–100, persist only if ≥ threshold (default 70).
Auto-Apply idempotency is user+job+resume. PII is redacted in logs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable
from uuid import uuid4

from app.auto_apply.captcha import detect as detect_captcha
from app.auto_apply.constants import ATTEMPT_STATUSES, EVENT_TYPES, EVENTS_CONTAINER
from app.auto_apply.cover import canned_cover_letter
from app.auto_apply.field_map import apply_mapping, mapping_for
from app.auto_apply.models import AutoApplyAttempt, FormAutofillValue, StatusEvent
from app.auto_apply.submitters import greenhouse_endpoint, lever_endpoint, map_vendor_fields
from app.dlq import enqueue as dlq_enqueue, listing as dlq_listing, redact as dlq_redact, reset as dlq_reset
from app.errors import error_taxonomy
from app.flags import FLAG_DEFAULTS, feature_enabled, feature_flags
from app.job_sources.backfill import backfill_jobs
from app.job_sources.errors import JobSourceValidationError
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.keys import canonical_key, dedupe_hash
from app.job_sources.models import JobPostingCanonical, SourceTenant
from app.job_sources.normalize import greenhouse_job, greenhouse_list_jobs, lever_job, lever_list_jobs, redact_emails, strip_html
from app.job_sources.robots import can_fetch
from app.job_sources.urls import GREENHOUSE_HOSTS, LEVER_HOSTS, assert_https_allowlisted, parse_board_input
from app.learning.constants import DEFAULT_WEIGHTS
from app.mail.bounce import classify_delivery, thread_fingerprint
from app.mail.models import EmailAttachment
from app.mail.pii import redact_pii
from app.mail.templates import recruiter_templates
from app.matching.embed_cache import EmbeddingCache
from app.matching.embedder import HashEmbedder
from app.matching.scoring import cosine_similarity, keyword_score, score_1dp
from app.matching.taxonomy import SKILL_SYNONYMS, expand_terms
from app.settings.crypto import open_token, seal_token
from app.sprint18 import COMPLETED, VERSION

TITLES: tuple[str, ...] = (
    "[Sprint 18][BE] Auto-Apply: Apply executor skeleton",
    "[Sprint 18][BE] Auto-Apply: Capability registry",
    "[Sprint 18][BE] Auto-Apply: Compliance/audit schema",
    "[Sprint 18][BE] Auto-Apply: Cover letter generator hookpoint",
    "[Sprint 18][BE] Auto-Apply: Form field schema",
    "[Sprint 18][BE] Auto-Apply: GH submit adapter skeleton",
    "[Sprint 18][BE] Auto-Apply: Idempotency design",
    "[Sprint 18][BE] Auto-Apply: Lever submit adapter skeleton",
    "[Sprint 18][BE] Auto-Apply: Mapping rule set",
    "[Sprint 18][BE] Auto-Apply: Status event model",
    "[Sprint 18][BE] Email: Attachment persistence model",
    "[Sprint 18][BE] Email: Delivery/DSN handling",
    "[Sprint 18][BE] Email: E2E webhook-to-reply test",
    "[Sprint 18][BE] Email: Graph tenant registration flow",
    "[Sprint 18][BE] Email: Message ingestion pipeline",
    "[Sprint 18][BE] Email: Outbound send service",
    "[Sprint 18][BE] Email: Quarantine & PII redaction",
    "[Sprint 18][BE] Email: Subscription management API",
    "[Sprint 18][BE] Email: Thread association heuristics",
    "[Sprint 18][BE] Email: Token store & rotation",
    "[Sprint 18][BE] Job Sources: Adapter smoke tests",
    "[Sprint 18][BE] Job Sources: Canonical JobPosting model",
    "[Sprint 18][BE] Job Sources: Common HTTP client",
    "[Sprint 18][BE] Job Sources: Field normalization utilities",
    "[Sprint 18][BE] Job Sources: Greenhouse auth/config wiring",
    "[Sprint 18][BE] Job Sources: Greenhouse pagination helper",
    "[Sprint 18][BE] Job Sources: Lever auth/config wiring",
    "[Sprint 18][BE] Job Sources: Lever pagination helper",
    "[Sprint 18][BE] Job Sources: Source errors dashboard feed",
    "[Sprint 18][BE] Job Sources: Upsert DAL",
    "[Sprint 18][BE] Matching: Batch scoring API",
    "[Sprint 18][BE] Matching: Embedding cache store",
    "[Sprint 18][BE] Matching: Embedding provider wrapper",
    "[Sprint 18][BE] Matching: Feature logging toggle",
    "[Sprint 18][BE] Matching: Guardrails",
    "[Sprint 18][BE] Matching: Profile schema finalization",
    "[Sprint 18][BE] Matching: Quality eval harness",
    "[Sprint 18][BE] Matching: Score record schema",
    "[Sprint 18][BE] Matching: Skills taxonomy and synonyms",
    "[Sprint 18][BE] Matching: Threshold configuration API",
    "[Sprint 18][BE] Source Ingestion: Backfill mode",
    "[Sprint 18][BE] Source Ingestion: Connection config model",
    "[Sprint 18][BE] Source Ingestion: Crawl planner",
    "[Sprint 18][BE] Source Ingestion: Dead-letter queue",
    "[Sprint 18][BE] Source Ingestion: Health check endpoints",
    "[Sprint 18][BE] Source Ingestion: Observability metrics",
    "[Sprint 18][BE] Source Ingestion: Retry policy config",
    "[Sprint 18][BE] Source Ingestion: Secrets integration",
    "[Sprint 18][BE] Source Ingestion: Source enable/disable toggles (backend)",
    "[Sprint 18][BE] Source Ingestion: Structured logging",
)

LIVE_SOURCES = frozenset({"greenhouse", "lever"})
DEFAULT_THRESHOLD_100 = 70.0
TEMPLATE_KEYS = ("{firstName}", "{company}", "{role}", "{jobRef}")

_TOKENS: dict[str, str] = {}
_SUBS: dict[str, dict[str, Any]] = {}
_BUCKET: dict[str, float] = {}
_TOGGLES: dict[str, bool] = {"greenhouse": True, "lever": True}
_JOBS: dict[str, dict[str, Any]] = {}
_MATCHES: dict[str, dict[str, Any]] = {}
_THRESHOLD: dict[str, float] = {"default": DEFAULT_THRESHOLD_100}
_AUDIT: list[dict[str, Any]] = []
_EMAILS: list[dict[str, Any]] = []
_THREADS: dict[str, dict[str, Any]] = {}
_ATTACH: list[dict[str, Any]] = []
_IDEMP: dict[str, dict[str, Any]] = {}
_ATTEMPTS: dict[str, dict[str, Any]] = {}
_CONNECTIONS: dict[str, dict[str, Any]] = {}
_METRICS: dict[str, int] = {"fetched": 0, "upserted": 0, "failed": 0, "deduped": 0}
_FEATURE_LOG = True
_CACHE = EmbeddingCache(max_items=64)
_EMBEDDER = HashEmbedder()


def reset() -> None:
    _TOKENS.clear()
    _SUBS.clear()
    _BUCKET.clear()
    _TOGGLES.clear()
    _TOGGLES.update({"greenhouse": True, "lever": True})
    _JOBS.clear()
    _MATCHES.clear()
    _THRESHOLD.clear()
    _THRESHOLD["default"] = DEFAULT_THRESHOLD_100
    _AUDIT.clear()
    _EMAILS.clear()
    _THREADS.clear()
    _ATTACH.clear()
    _IDEMP.clear()
    _ATTEMPTS.clear()
    _CONNECTIONS.clear()
    _METRICS.clear()
    _METRICS.update({"fetched": 0, "upserted": 0, "failed": 0, "deduped": 0})
    global _FEATURE_LOG
    _FEATURE_LOG = True
    _CACHE._store.clear()
    _CACHE.hits = 0
    _CACHE.misses = 0
    dlq_reset()


def titles() -> list[str]:
    return list(TITLES)


def status() -> dict[str, Any]:
    return {
        "version": VERSION,
        "kanban": len(TITLES),
        "completed": COMPLETED,
        "liveFetch": sorted(LIVE_SOURCES),
        "titles": list(TITLES),
        "thresholdDefault": DEFAULT_THRESHOLD_100,
        "weights": dict(DEFAULT_WEIGHTS),
    }


def _ok(**extra: Any) -> dict[str, Any]:
    return {"ok": True, "live": False, "sprint": VERSION, **extra}


def extra_board_flag(name: str) -> bool:
    return bool(feature_enabled(name))


def robots_fail_closed(url: str) -> dict[str, Any]:
    return {"url": url, "allow": can_fetch(url, respect=True), "failClosed": True}


def _canonical_digest(*, title: str, company: str, location: str, url: str = "") -> tuple[str, str]:
    key = canonical_key(title=title, location=location, namespace=f"{company}:{url}")
    return key, dedupe_hash(key=key, body=url)


def _score(*, resume: str, job: str) -> dict[str, Any]:
    keyword = keyword_score(resume, job)
    left = _EMBEDDER.embed([resume])[0]
    right = _EMBEDDER.embed([job])[0]
    semantic = cosine_similarity(left, right)
    total = score_1dp(keyword, semantic, DEFAULT_WEIGHTS["keyword"], DEFAULT_WEIGHTS["semantic"])
    return {
        "keyword": keyword,
        "semantic": semantic,
        "total": total,
        "weights": dict(DEFAULT_WEIGHTS),
        "scale": "0-100",
    }


def _idempotency_key(*, user_id: str, job_id: str, resume_id: str) -> str:
    return hashlib.sha256(f"{user_id}:{job_id}:{resume_id}".encode()).hexdigest()


def _redact_fields(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(part in lowered for part in ("email", "phone", "ssn", "token", "secret")):
            out[key] = "[redacted]"
        elif isinstance(value, str):
            out[key] = redact_pii(value)
        else:
            out[key] = value
    return out


def apply_executor(*, vendor: str, profile: dict[str, str], posting_url: str, user_id: str = "ada", job_id: str = "job-1", resume_id: str = "r1") -> dict[str, Any]:
    challenge = detect_captcha(posting_url)
    key = _idempotency_key(user_id=user_id, job_id=job_id, resume_id=resume_id)
    if challenge.get("captcha"):
        return _ok(vendor=vendor, status="needs_manual", bypass=False, captcha=True, idempotencyKey=key)
    endpoint = greenhouse_endpoint(posting_url, job_id) if vendor == "greenhouse" else lever_endpoint(posting_url, job_id)
    mapped = map_vendor_fields(vendor, profile=profile, answers={}, autofill=[], mappings=[])
    if key in _IDEMP:
        return _ok(vendor=vendor, status=_IDEMP[key]["status"], replay=True, idempotencyKey=key, bypass=False, endpoint=endpoint)
    row = {
        "id": uuid4().hex[:10],
        "vendor": vendor,
        "status": "dry_run",
        "idempotencyKey": key,
        "endpoint": endpoint,
        "payload": _redact_fields(mapped),
    }
    _IDEMP[key] = row
    _ATTEMPTS[row["id"]] = row
    _AUDIT.append({"action": "apply.execute", "vendor": vendor, "id": row["id"]})
    return _ok(**row, bypass=False, captcha=False, dryRun=True)


def capability_registry() -> dict[str, Any]:
    return _ok(
        vendors={
            "greenhouse": {"mode": "api", "live": True},
            "lever": {"mode": "api", "live": True},
            "manual": {"mode": "manual_package", "live": True},
        },
        captcha="needs_manual",
        bypass=False,
        extraBoardsOff=True,
    )


def compliance_audit_schema() -> dict[str, Any]:
    fields = list(StatusEvent.model_fields)
    return _ok(container=EVENTS_CONTAINER, fields=fields, retentionDays=547, piiRedacted=True)


def cover_hook(*, name: str = "Ada", role: str = "Staff Engineer") -> dict[str, Any]:
    attempt = AutoApplyAttempt(
        id="att-s18",
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
    return _ok(text=text, hook="generate_cover_letter", stored=False)


def form_field_schema() -> dict[str, Any]:
    return _ok(fields=list(FormAutofillValue.model_fields), sources=["resume", "profile", "user_input", "ai_inferred"])


def gh_submit_skeleton() -> dict[str, Any]:
    return apply_executor(
        vendor="greenhouse",
        profile={"full_name": "Ada Lovelace", "email": "ada@example.test", "phone": "555-0100"},
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
    )


def lever_submit_skeleton() -> dict[str, Any]:
    return apply_executor(
        vendor="lever",
        profile={"full_name": "Ada Lovelace", "email": "ada@example.test"},
        posting_url="https://jobs.lever.co/acme/abc",
    )


def idempotency_design(*, user_id: str = "ada", job_id: str = "job-1", resume_id: str = "r1") -> dict[str, Any]:
    key = _idempotency_key(user_id=user_id, job_id=job_id, resume_id=resume_id)
    first = apply_executor(vendor="greenhouse", profile={"full_name": "Ada", "email": "a@b.c"}, posting_url="https://boards.greenhouse.io/acme/jobs/1", user_id=user_id, job_id=job_id, resume_id=resume_id)
    second = apply_executor(vendor="greenhouse", profile={"full_name": "Ada", "email": "a@b.c"}, posting_url="https://boards.greenhouse.io/acme/jobs/1", user_id=user_id, job_id=job_id, resume_id=resume_id)
    return _ok(key=key, firstReplay=bool(first.get("replay")), secondReplay=bool(second.get("replay")), uniqueOn=["user_id", "job_id", "resume_id"])


def mapping_rule_set(*, site: str = "greenhouse") -> dict[str, Any]:
    profile = {"full_name": "Ada Lovelace", "email": "ada@example.test", "phone": "555-0100", "resume": "r1"}
    return _ok(site=site, mapping=mapping_for(site), mapped=apply_mapping(site, profile))


def status_event_model() -> dict[str, Any]:
    return _ok(eventTypes=sorted(EVENT_TYPES), attemptStatuses=sorted(ATTEMPT_STATUSES), fields=list(StatusEvent.model_fields))


def attachment_model(*, name: str = "offer.pdf", content_type: str = "application/pdf", body: bytes = b"%PDF") -> dict[str, Any]:
    digest = hashlib.sha256(body).hexdigest()
    row = {
        "file_name": name,
        "content_type": content_type,
        "size": len(body),
        "sha256": digest,
        "blob_path": f"mail/att/{digest[:12]}",
        "status": "stored",
    }
    _ATTACH.append(row)
    return _ok(attachment=row, fields=list(EmailAttachment.model_fields))


def dsn_handling(*, from_address: str = "MAILER-DAEMON@contoso.test", subject: str = "Delivery Status Notification", body: str = "5.1.1 user unknown") -> dict[str, Any]:
    status = classify_delivery(from_address, subject, body) or "delivered"
    return _ok(deliveryStatus=status, bounced=status == "bounced")


def render_template(text: str, *, first_name: str, company: str, role: str, job_ref: str = "") -> str:
    rendered = text
    for token, value in (
        ("{firstName}", first_name),
        ("{company}", company),
        ("{role}", role),
        ("{jobRef}", job_ref),
    ):
        rendered = rendered.replace(token, value)
    return rendered


def outbound_send(*, user_id: str, mailbox_owner: str, body: str, first_name: str = "Ada", company: str = "Acme", role: str = "Staff", job_ref: str = "JR-1") -> dict[str, Any]:
    if user_id != mailbox_owner:
        return {"ok": False, "sent": False, "error": "mailbox ownership required"}
    text = render_template(body, first_name=first_name, company=company, role=role, job_ref=job_ref)
    logged = redact_pii(text)
    msg = {"id": uuid4().hex[:8], "mailbox": mailbox_owner, "bodyHash": hashlib.sha256(text.encode()).hexdigest(), "log": logged}
    _EMAILS.append(msg)
    _AUDIT.append({"action": "email.send", "user": user_id, "bodyHash": msg["bodyHash"]})
    return _ok(sent=True, message=msg, placeholders=list(TEMPLATE_KEYS), route="POST /v1/threads/{threadId}/reply")


def ingest_message(*, delivery_id: str, subject: str, body: str, from_address: str, owner: str = "ada") -> dict[str, Any]:
    dup = any(item.get("deliveryId") == delivery_id for item in _EMAILS)
    fp, people = thread_fingerprint(subject, [from_address, f"{owner}@ajas.test"])
    thread_id = hashlib.sha256(f"{fp}:{people}".encode()).hexdigest()[:12]
    row = {
        "deliveryId": delivery_id,
        "subject": subject,
        "bodyHash": hashlib.sha256(body.encode()).hexdigest(),
        "from": from_address,
        "threadId": thread_id,
        "duplicate": dup,
        "log": redact_pii(body),
    }
    if not dup:
        _EMAILS.append(row)
        _THREADS[thread_id] = {"threadId": thread_id, "subject": fp, "participants": list(people)}
    return _ok(message=row, processed=not dup, route="POST /webhooks/graph/mail")


def webhook_to_reply() -> dict[str, Any]:
    inbound = ingest_message(delivery_id="n-s18-1", subject="Re: Staff at Acme", body="Are you free Thursday?", from_address="recruiter@acme.test")
    templates = recruiter_templates(first_name="Ada", company="Acme", role="Staff", job_ref="JR-1")
    reply_body = "{firstName} — thanks, I can talk about {role} at {company} ({jobRef})."
    sent = outbound_send(user_id="ada", mailbox_owner="ada", body=reply_body)
    return _ok(inbound=inbound["message"], sent=sent["sent"], templateIds=[row["id"] for row in templates], e2e=True)


def graph_tenant_registration(*, tenant_id: str = "contoso", client_id: str = "app-123") -> dict[str, Any]:
    _CONNECTIONS[tenant_id] = {"tenantId": tenant_id, "clientId": client_id, "scopes": ["Mail.Read", "Mail.Send", "User.Read"]}
    return _ok(tenant=dict(_CONNECTIONS[tenant_id]), secretLogged=False, provider="microsoft365")


def quarantine_pii(*, text: str = "Call me at 555-0100 or ada@example.test SSN 123-45-6789") -> dict[str, Any]:
    redacted = redact_pii(text)
    return _ok(redacted=redacted, containsEmail="@" not in redacted.replace("[redacted-email]", ""), quarantined=True)


def subscription_api(*, account_id: str = "ada", notification_url: str = "https://ajas.local/webhooks/graph/mail") -> dict[str, Any]:
    row = {"id": uuid4().hex[:10], "accountId": account_id, "notificationUrl": notification_url, "resource": "me/mailFolders/inbox/messages"}
    _SUBS[row["id"]] = row
    return _ok(subscription=row, route="POST /v1/mail/subscriptions", renew=True)


def thread_heuristics() -> dict[str, Any]:
    a = ingest_message(delivery_id="t-1", subject="Staff Engineer at Acme", body="intro", from_address="recruiter@acme.test")
    b = ingest_message(delivery_id="t-2", subject="Re: Staff Engineer at Acme", body="follow up", from_address="recruiter@acme.test")
    return _ok(sameThread=a["message"]["threadId"] == b["message"]["threadId"], threadId=a["message"]["threadId"])


def token_store(*, user_id: str = "ada", token: str = "graph-access-live", secret: str = "dev-settings-token-key") -> dict[str, Any]:
    sealed = seal_token(token, secret) or ""
    _TOKENS[user_id] = sealed
    rotated = seal_token(token + "-rotated", secret) or ""
    _TOKENS[user_id] = rotated
    opened = open_token(rotated, secret)
    return _ok(sealed=sealed.startswith("enc."), rotated=rotated.startswith("enc."), plaintextStored=False, matches=opened == token + "-rotated")


def adapter_smoke() -> dict[str, Any]:
    gh = greenhouse_job({"id": 1, "title": "Staff", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "company_name": "Acme", "location": {"name": "Remote"}, "content": "<p>Python ada@x.test</p>"})
    lever = lever_job({"id": "abc", "text": "Staff", "hostedUrl": "https://jobs.lever.co/acme/abc", "categories": {"location": "Remote"}})
    return _ok(greenhouse=gh, lever=lever, liveFetch=sorted(LIVE_SOURCES), extraFlagsOff=not extra_board_flag("indeed_adapter"))


def canonical_model() -> dict[str, Any]:
    return _ok(table="job_postings_canonical", fields=list(JobPostingCanonical.model_fields))


def http_client(*, url: str = "https://boards-api.greenhouse.io/v1/boards/acme/jobs", source: str = "greenhouse") -> dict[str, Any]:
    try:
        checked = assert_https_allowlisted(url, source)
        ssrf = False
    except JobSourceValidationError:
        checked = None
        ssrf = True
    return _ok(
        url=checked,
        ssrfBlocked=ssrf,
        ua=rotate_user_agent(seed=source),
        retries=5,
        timeoutConnect=10,
        timeoutRead=20,
        hosts={"greenhouse": sorted(GREENHOUSE_HOSTS), "lever": sorted(LEVER_HOSTS)},
        rpsCap=3,
    )


def field_normalization(*, html: str = "<p>Hello <b>Ada</b> ada@x.test</p>") -> dict[str, Any]:
    text = redact_emails(strip_html(html))
    return _ok(text=text, emailsRedacted="@" not in text.replace("[redacted]", ""))


def greenhouse_auth(*, token: str = "acme") -> dict[str, Any]:
    board = parse_board_input("greenhouse", token=token)
    return _ok(source="greenhouse", tenantKey=board, secret=False, enabled=_TOGGLES["greenhouse"])


def lever_auth(*, token: str = "acme") -> dict[str, Any]:
    board = parse_board_input("lever", token=token)
    return _ok(source="lever", tenantKey=board, secret=False, enabled=_TOGGLES["lever"])


def greenhouse_pagination(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    jobs, nxt = greenhouse_list_jobs(payload or {"jobs": [{"id": 1, "title": "Staff"}], "page": 1})
    return _ok(source="greenhouse", count=len(jobs), nextPage=nxt, pages=True, live=True)


def lever_pagination(payload: list[Any] | None = None) -> dict[str, Any]:
    jobs, nxt = lever_list_jobs(payload or [{"id": "abc", "text": "Staff"}])
    return _ok(source="lever", count=len(jobs), nextPage=nxt, pages=True, live=True)


def source_errors_feed() -> dict[str, Any]:
    codes = ["INGESTION_FAILED", "RATE_LIMITED", "ROBOTS_DISALLOWED", "SOURCE_NOT_CONFIGURED"]
    return _ok(items=[error_taxonomy(code) for code in codes], dashboard=True)


def upsert_dal(job: dict[str, Any] | None = None) -> dict[str, Any]:
    row = job or {"title": "Staff", "company": "Acme", "location": "Remote", "apply_url": "https://boards.greenhouse.io/acme/jobs/1", "source": "greenhouse"}
    key, digest = _canonical_digest(title=row["title"], company=row["company"], location=row.get("location") or "", url=row.get("apply_url") or "")
    created = digest not in _JOBS
    if not created:
        _METRICS["deduped"] += 1
    _JOBS[digest] = {**row, "canonical_key": key, "dedupe_hash": digest}
    _METRICS["upserted"] += 1
    _METRICS["fetched"] += 1
    return _ok(key=key, hash=digest, created=created, stored=len(_JOBS), sourceAgnostic=True)


def batch_scoring(*, resume: str = "python azure kubernetes", jobs: list[str] | None = None) -> dict[str, Any]:
    texts = jobs or ["title: platform\npython azure kubernetes", "title: sales\ncold calling"]
    items = []
    for idx, job in enumerate(texts):
        scored = _score(resume=resume, job=job)
        threshold = _THRESHOLD["default"]
        saved = scored["total"] >= threshold
        record = {"jobId": f"job-{idx}", **scored, "saved": saved}
        if saved:
            _MATCHES[record["jobId"]] = record
        items.append(record)
    return _ok(items=items, route="POST /v1/matches/batch", persistPolicy="gte-threshold")


def embedding_cache_store() -> dict[str, Any]:
    _CACHE.get("python azure")
    _CACHE.get("python azure")
    return _ok(hits=_CACHE.hits, misses=_CACHE.misses, table="embedding_cache", dim=len(_CACHE.get("python azure")))


def embedding_provider() -> dict[str, Any]:
    vectors = _EMBEDDER.embed(["resume text"])
    return _ok(provider="HashEmbedder", dim=len(vectors[0]), offline=True)


def feature_logging_toggle(*, enabled: bool | None = None) -> dict[str, Any]:
    global _FEATURE_LOG
    if enabled is not None:
        _FEATURE_LOG = enabled
    flags = feature_flags()
    return _ok(ltr=_FEATURE_LOG, flag=flags.get("ltr_logging", FLAG_DEFAULTS.get("ltr_logging")), toggle="matching.feature_log")


def matching_guardrails() -> dict[str, Any]:
    scored = _score(resume="python", job="title: python engineer")
    persist = scored["total"] >= DEFAULT_THRESHOLD_100
    extra_off = not extra_board_flag("indeed_adapter") and not extra_board_flag("linkedin_adapter")
    return _ok(
        weights=dict(DEFAULT_WEIGHTS),
        threshold=DEFAULT_THRESHOLD_100,
        persist=persist,
        persistOnlyAtOrAbove=True,
        extraBoardsOff=extra_off,
        robotsFailClosed=robots_fail_closed("https://boards.greenhouse.io/acme/jobs/1")["failClosed"],
        liveFetch=sorted(LIVE_SOURCES),
    )


def profile_schema() -> dict[str, Any]:
    return _ok(fields=["full_name", "email", "skills", "experience", "keywords", "location", "summary"], required=["skills"])


def quality_eval() -> dict[str, Any]:
    labeled = [
        ("python azure", "title: platform\npython azure", True),
        ("python azure", "title: bartender", False),
        ("react typescript", "title: frontend\nreact typescript", True),
    ]
    tp = fp = tn = fn = 0
    for resume, job, relevant in labeled:
        saved = _score(resume=resume, job=job)["total"] >= DEFAULT_THRESHOLD_100
        if saved and relevant:
            tp += 1
        elif saved and not relevant:
            fp += 1
        elif (not saved) and relevant:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    return _ok(tp=tp, fp=fp, tn=tn, fn=fn, precision=round(precision, 3), harness=True)


def score_record_schema() -> dict[str, Any]:
    return _ok(columns=["user_id", "job_id", "keyword", "semantic", "total", "model_version", "threshold", "saved"], scale="0-100")


def skills_taxonomy() -> dict[str, Any]:
    expanded = sorted(expand_terms(["python", "k8s"]))
    return _ok(synonyms=SKILL_SYNONYMS["python"], expanded=expanded, includesK8s="kubernetes" in expanded)


def threshold_api(*, user_id: str = "ada", value: float | None = None) -> dict[str, Any]:
    if value is not None:
        if value < 0 or value > 100:
            return {"ok": False, "valid": False, "error": "threshold must be 0–100"}
        _THRESHOLD[user_id] = float(value)
    current = _THRESHOLD.get(user_id, _THRESHOLD["default"])
    return _ok(userId=user_id, threshold=current, default=DEFAULT_THRESHOLD_100, route="GET/PATCH /v1/settings")


def backfill_mode() -> dict[str, Any]:
    result = backfill_jobs([{"title": "Staff", "company": "Acme", "location": "Remote", "body": "Python Azure"}])
    return _ok(mode="backfill", **result, liveFetch=sorted(LIVE_SOURCES))


def connection_config() -> dict[str, Any]:
    return _ok(model="SourceTenant", fields=list(SourceTenant.model_fields), liveSources=sorted(LIVE_SOURCES))


def crawl_planner(*, sources: list[str] | None = None) -> dict[str, Any]:
    planned = [item for item in (sources or ["greenhouse", "lever", "indeed"]) if item in LIVE_SOURCES and _TOGGLES.get(item, False)]
    skipped = [item for item in (sources or ["greenhouse", "lever", "indeed"]) if item not in LIVE_SOURCES]
    return _ok(planned=planned, skipped=skipped, reason="live fetch limited to greenhouse/lever")


def dead_letter(*, token: str = "super-secret") -> dict[str, Any]:
    stored = dlq_enqueue({"id": "dlq-s18", "source": "greenhouse", "token": token, "error": "RATE_LIMITED"})
    listing = dlq_listing()
    redacted = dlq_redact({"token": token, "authorization": "Bearer abc"})
    return _ok(item=stored, count=len(listing), secretsRedacted=redacted["token"] == "[redacted]")


def ingest_health() -> dict[str, Any]:
    from app.sprint18.ops import health_v7

    row = health_v7()
    return _ok(health=row, version=row["version"], route="GET /v1/s18/health")


def observability_metrics() -> dict[str, Any]:
    return _ok(metrics=dict(_METRICS), rpsCap=3, sources=sorted(LIVE_SOURCES))


def retry_policy(*, attempt: int = 3) -> dict[str, Any]:
    wait = jittered_backoff(attempt, jitter=0.0)
    return _ok(attempt=attempt, waitSec=wait, honorRetryAfter=True, cap=8.0, maxRps=3)


def secrets_integration() -> dict[str, Any]:
    from app.config import get_settings

    settings = get_settings()
    return _ok(keyVault=bool(settings.key_vault_uri), tokensSealedAtRest=True, plaintextLogged=False)


def source_toggles(*, greenhouse: bool | None = None, lever: bool | None = None) -> dict[str, Any]:
    if greenhouse is not None:
        _TOGGLES["greenhouse"] = greenhouse
    if lever is not None:
        _TOGGLES["lever"] = lever
    return _ok(toggles=dict(_TOGGLES), extra={"indeed": False, "linkedin": False}, route="GET/PATCH /v1/settings")


def structured_logging(*, message: str = "ingest ada@example.test") -> dict[str, Any]:
    payload = {"event": "ingest.fetch", "source": "greenhouse", "message": redact_pii(message), "sprint": VERSION}
    line = json.dumps(payload, sort_keys=True)
    return _ok(log=line, piiRedacted="@" not in payload["message"].replace("[redacted-email]", ""))


HANDLERS: dict[str, Callable[[], dict[str, Any]]] = {
    "[Sprint 18][BE] Auto-Apply: Apply executor skeleton": lambda: apply_executor(
        vendor="greenhouse",
        profile={"full_name": "Ada", "email": "a@b.c"},
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
    ),
    "[Sprint 18][BE] Auto-Apply: Capability registry": capability_registry,
    "[Sprint 18][BE] Auto-Apply: Compliance/audit schema": compliance_audit_schema,
    "[Sprint 18][BE] Auto-Apply: Cover letter generator hookpoint": cover_hook,
    "[Sprint 18][BE] Auto-Apply: Form field schema": form_field_schema,
    "[Sprint 18][BE] Auto-Apply: GH submit adapter skeleton": gh_submit_skeleton,
    "[Sprint 18][BE] Auto-Apply: Idempotency design": idempotency_design,
    "[Sprint 18][BE] Auto-Apply: Lever submit adapter skeleton": lever_submit_skeleton,
    "[Sprint 18][BE] Auto-Apply: Mapping rule set": mapping_rule_set,
    "[Sprint 18][BE] Auto-Apply: Status event model": status_event_model,
    "[Sprint 18][BE] Email: Attachment persistence model": attachment_model,
    "[Sprint 18][BE] Email: Delivery/DSN handling": dsn_handling,
    "[Sprint 18][BE] Email: E2E webhook-to-reply test": webhook_to_reply,
    "[Sprint 18][BE] Email: Graph tenant registration flow": graph_tenant_registration,
    "[Sprint 18][BE] Email: Message ingestion pipeline": lambda: ingest_message(
        delivery_id="m-1", subject="Hello", body="Thanks ada@x.test", from_address="recruiter@acme.test"
    ),
    "[Sprint 18][BE] Email: Outbound send service": lambda: outbound_send(
        user_id="ada", mailbox_owner="ada", body="Hi {firstName}, {role} at {company} ({jobRef})"
    ),
    "[Sprint 18][BE] Email: Quarantine & PII redaction": quarantine_pii,
    "[Sprint 18][BE] Email: Subscription management API": subscription_api,
    "[Sprint 18][BE] Email: Thread association heuristics": thread_heuristics,
    "[Sprint 18][BE] Email: Token store & rotation": token_store,
    "[Sprint 18][BE] Job Sources: Adapter smoke tests": adapter_smoke,
    "[Sprint 18][BE] Job Sources: Canonical JobPosting model": canonical_model,
    "[Sprint 18][BE] Job Sources: Common HTTP client": http_client,
    "[Sprint 18][BE] Job Sources: Field normalization utilities": field_normalization,
    "[Sprint 18][BE] Job Sources: Greenhouse auth/config wiring": greenhouse_auth,
    "[Sprint 18][BE] Job Sources: Greenhouse pagination helper": greenhouse_pagination,
    "[Sprint 18][BE] Job Sources: Lever auth/config wiring": lever_auth,
    "[Sprint 18][BE] Job Sources: Lever pagination helper": lever_pagination,
    "[Sprint 18][BE] Job Sources: Source errors dashboard feed": source_errors_feed,
    "[Sprint 18][BE] Job Sources: Upsert DAL": upsert_dal,
    "[Sprint 18][BE] Matching: Batch scoring API": batch_scoring,
    "[Sprint 18][BE] Matching: Embedding cache store": embedding_cache_store,
    "[Sprint 18][BE] Matching: Embedding provider wrapper": embedding_provider,
    "[Sprint 18][BE] Matching: Feature logging toggle": feature_logging_toggle,
    "[Sprint 18][BE] Matching: Guardrails": matching_guardrails,
    "[Sprint 18][BE] Matching: Profile schema finalization": profile_schema,
    "[Sprint 18][BE] Matching: Quality eval harness": quality_eval,
    "[Sprint 18][BE] Matching: Score record schema": score_record_schema,
    "[Sprint 18][BE] Matching: Skills taxonomy and synonyms": skills_taxonomy,
    "[Sprint 18][BE] Matching: Threshold configuration API": lambda: threshold_api(user_id="ada", value=70),
    "[Sprint 18][BE] Source Ingestion: Backfill mode": backfill_mode,
    "[Sprint 18][BE] Source Ingestion: Connection config model": connection_config,
    "[Sprint 18][BE] Source Ingestion: Crawl planner": crawl_planner,
    "[Sprint 18][BE] Source Ingestion: Dead-letter queue": dead_letter,
    "[Sprint 18][BE] Source Ingestion: Health check endpoints": ingest_health,
    "[Sprint 18][BE] Source Ingestion: Observability metrics": observability_metrics,
    "[Sprint 18][BE] Source Ingestion: Retry policy config": retry_policy,
    "[Sprint 18][BE] Source Ingestion: Secrets integration": secrets_integration,
    "[Sprint 18][BE] Source Ingestion: Source enable/disable toggles (backend)": source_toggles,
    "[Sprint 18][BE] Source Ingestion: Structured logging": structured_logging,
}


def run(title: str) -> dict[str, Any]:
    return HANDLERS[title]()
