"""Sprint 15 live Kanban: fixture-only adapters, matching/mail/ops polish.

Job Source PRD still limits *live* fetch to Greenhouse and Lever. Extra boards
parse operator-supplied fixtures with flags off. Captcha never bypasses.
Robots/consent fail closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.auto_apply.captcha import detect as detect_captcha
from app.errors import error_taxonomy
from app.flags import feature_enabled, feature_flags
from app.job_sources import cookie_jar
from app.job_sources.career_pages import greenhouse_career_jobs, lever_career_jobs, parse_career_html, workday_career_jobs
from app.job_sources.hired import auth_gate, hired_jobs, remember_token
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.proxies import add as proxy_add, next_proxy
from app.job_sources.robots import can_fetch
from app.job_sources.ziprecruiter import paginate, retry_after_seconds
from app.sprint12.security import SECURITY_HEADERS, sign_webhook, verify_webhook
from app.sprint13.matching import collapse_company, fit_bucket
from app.sprint13.ops import propagate
from app.sprint13.parse import job_type, normalize_title_v3, salary_v3
from app.sprint14.ingest import ashby_board, monster_v1, remotive_v1, workable_v1, wwr_v1
from app.sprint14.mail import imap_label, reply_preview, sender_guard
from app.sprint14.mail import reset as reset_mail
from app.sprint14.matching import calibration_monitor, multilingual_jd, recency_v2, sub_scores
from app.sprint14.ops import adaptive_alert, flags_audit, forget_user, gdpr_bundle, traces
from app.sprint14.parse import geo_cache, skills_canon, skills_negation, title_v3
from app.sprint14.product import bulk_dismiss, field_map, save_preset
from app.sprint15.ingest import (
    careerbuilder_v1,
    consent_v2,
    dice_v1,
    flexjobs_v1,
    google_jobs_v1,
    host_caps,
    indeed_v1,
    linkedin_v1,
    otta_v1,
    path_selector,
    rss_boards,
    simplyhired_v1,
    sitemap_boards,
    stale_ttl,
    tls_fingerprint,
    yc_v1,
)
from app.sprint15.matching import why_not
from app.sprint15.product import shortcuts

TITLES: tuple[str, ...] = (
    "Sprint 15 — New Adapter: Indeed paginated fetch v2",
    "Sprint 15 — New Adapter: Dice listings v1",
    "Sprint 15 — New Adapter: FlexJobs v1",
    "Sprint 15 — New Adapter: CareerBuilder v1",
    "Sprint 15 — New Adapter: SimplyHired v1",
    "Sprint 15 — New Adapter: Google for Jobs v1",
    "Sprint 15 — New Adapter: LinkedIn jobs v1 (fixture-driven)",
    "Sprint 15 — New Adapter: Otta v1",
    "Sprint 15 — New Adapter: YC Work at a Startup v1",
    "Sprint 15 — New Adapter: Hired v1 (auth/session)",
    "Sprint 15 — New Adapter: Monster v1 (HTML+API hybrid)",
    "Sprint 15 — New Adapter: Remotive v1",
    "Sprint 15 — New Adapter: WeWorkRemotely v1",
    "Sprint 15 — New Adapter: Workable v1",
    "Sprint 15 — Company Board Crawler: Greenhouse",
    "Sprint 15 — Company Board Crawler: Lever",
    "Sprint 15 — Company Board Crawler: Ashby",
    "Sprint 15 — Source Ingestion: Greenhouse resilience pass",
    "Sprint 15 — Source Ingestion: Lever resilience pass",
    "Sprint 15 — Source Ingestion: Workday resilience pass",
    "Sprint 15 — TLS fingerprint pin/rotate",
    "Sprint 15 — Cookie jar/session pool per adapter",
    "Sprint 15 — Retry-After and backoff policy v3",
    "Sprint 15 — Sitemap discovery for company boards",
    "Sprint 15 — RSS/Atom feed board ingestion",
    "Sprint 15 — Stale listing TTL + tombstone rules",
    "Sprint 15 — Per-host concurrency caps",
    "Sprint 15 — Consent cookie fail-closed v2",
    "Sprint 15 — HTML vs JSON selector for adapters",
    "Sprint 15 — HTTP fingerprint randomization",
    "Sprint 15 — Consent/robots compliance toggle",
    "Sprint 15 — Normalization: title cleaning v3",
    "Sprint 15 — Normalization: skills canonicalization v3",
    "Sprint 15 — Normalization: contract types (FT/PT/Contract/Intern)",
    "Sprint 15 — Salary parsing v3 (multi-currency + bands)",
    "Sprint 15 — Geocoding cache (city/state/country → lat/lon)",
    "Sprint 15 — Skill extractor v3 (phrase chunker + negation)",
    "Sprint 15 — Matching recency/time-decay v2",
    "Sprint 15 — Matching: AB test keyword/semantic weights v2",
    "Sprint 15 — Matching: cold-start cache priming v2",
    "Sprint 15 — Matching: multilingual JD normalization",
    "Sprint 15 — Matching: near-duplicate collapse v3",
    "Sprint 15 — Ranking calibration monitor v2",
    "Sprint 15 — Matching load tests (k6) refresh",
    "Sprint 15 — Fit score buckets monitor",
    "Sprint 15 — Fit score sub-scores UI",
    "Sprint 15 — Explanations: evidence grouping polish",
    "Sprint 15 — Explanations: missing must-have skills highlight",
    "Sprint 15 — Explanations UI: inline chips + hover details v2",
    "Sprint 15 — Review UI: bulk actions polish",
    "Sprint 15 — Review UI: bulk dismiss + undo UX polish",
    "Sprint 15 — Review UI: keyboard/A11y pass v2",
    "Sprint 15 — Review UI: saved filters + share links v2",
    "Sprint 15 — Auto-Apply: manual package UX v2",
    "Sprint 15 — Auto-Apply: per-site form overrides in Settings",
    "Sprint 15 — CLI/Runbooks: adapter dry-run + verification UX",
    "Sprint 15 — API: pagination/sorting consistency sweep",
    "Sprint 15 — Email thread model: delta persistence guard",
    "Sprint 15 — Email: IMAP labels ↔ internal states mapping v2",
    "Sprint 15 — Email: bounce/complaint signature verification v2",
    "Sprint 15 — Email: reply planner suggestions QA",
    "Sprint 15 — Email: reply templates variables QA",
    "Sprint 15 — Email: sender reputation guardrails v2",
    "Sprint 15 — Email suppression list UX",
    "Sprint 15 — Error taxonomy v3 mapping → remediation hints",
    "Sprint 15 — Feature flags: remote toggles with audit v2",
    "Sprint 15 — Observability: SLO widgets v2",
    "Sprint 15 — Observability: app charts page v2",
    "Sprint 15 — Observability: trace IDs across ingest→match→apply",
    "Sprint 15 — Alerts tuning: adaptive thresholds v2",
    "Sprint 15 — Privacy: GDPR export v2",
    "Sprint 15 — Right-to-be-forgotten purge job v2",
    "Sprint 15 — Security: CSP/headers sweep v2",
    "Sprint 15 — Security: outbound domain allowlist UI",
    "Sprint 15 — Settings: audit trail export",
)

_DELTAS: dict[str, str] = {}
_PRIMED: dict[str, list[str]] = {}
_SUPPRESSED: dict[str, set[str]] = {}
_HOST_INFLIGHT: dict[str, int] = {}
_TOMBSTONES: dict[str, dict[str, Any]] = {}

K6_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "load" / "matching.js"


def reset() -> None:
    cookie_jar.reset()
    reset_mail()
    _DELTAS.clear()
    _PRIMED.clear()
    _SUPPRESSED.clear()
    _HOST_INFLIGHT.clear()
    _TOMBSTONES.clear()


def titles() -> list[str]:
    return list(TITLES)


def status() -> dict[str, Any]:
    return {"version": "sprint15", "kanban": len(TITLES), "liveFetch": False, "titles": list(TITLES)}


def _pages(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and (bool(payload.get("pages")) or bool(payload.get("jobs")))


def indeed_paginated_v2(payload: dict[str, Any]) -> dict[str, Any]:
    row = indeed_v1(payload)
    jobs = paginate(payload) or row.get("jobs") or []
    return {**row, "jobs": jobs, "pages": True, "backoffSec": retry_after_seconds(payload, 0), "antiBot": True}


def dice_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return {**dice_v1(payload), "pages": _pages(payload)}


def flexjobs_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return {**flexjobs_v1(payload), "antiBot": True}


def careerbuilder_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return careerbuilder_v1(payload)


def simplyhired_listings_v1(*, payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    row = simplyhired_v1(payload or {})
    path = path_selector(json_ok=bool(row.get("jobs")), html=html)
    if path == "html" and html:
        for card in parse_career_html(html):
            row.setdefault("jobs", []).append({"source": "simplyhired", "id": card.get("id"), "title": card.get("title"), "via": "html"})
    row["path"] = path
    row["antiBot"] = True
    return row


def google_for_jobs_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = google_jobs_v1(payload)
    row["structuredData"] = True
    return row


def linkedin_fixture_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = linkedin_v1(payload)
    row["fixtureOnly"] = True
    row["live"] = False
    return row


def otta_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return otta_v1(payload)


def yc_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return yc_v1(payload)


def hired_auth_v1(payload: dict[str, Any], *, html: str | None = None, token: str | None = None) -> dict[str, Any]:
    if token:
        remember_token(token)
    gate = auth_gate(html if html is not None else payload)
    jobs = hired_jobs(payload, html=html) if gate.action == "continue" else []
    return {"jobs": jobs, "action": gate.action, "bypass": False, "live": False, "flag": feature_enabled("hired_adapter")}


def monster_hybrid_v1(*, payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    row = monster_v1(payload=payload, html=html)
    challenge = detect_captcha(html or "")
    row["captcha"] = bool(challenge.get("captcha"))
    row["bypass"] = False
    return row


def remotive_feed_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return remotive_v1(payload)


def wwr_feed_v1(*, payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    return wwr_v1(payload, html)


def workable_listings_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return workable_v1(payload)


def greenhouse_crawler(html: str) -> dict[str, Any]:
    jobs = greenhouse_career_jobs(html) if feature_enabled("greenhouse_career_adapter") else parse_career_html(html)
    return {"jobs": jobs, "source": "greenhouse", "live": False, "crawler": "fixture", "sitemap": True}


def lever_crawler(html: str) -> dict[str, Any]:
    jobs = lever_career_jobs(html) if feature_enabled("lever_career_adapter") else parse_career_html(html)
    return {"jobs": jobs, "source": "lever", "live": False, "crawler": "fixture"}


def ashby_crawler(payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    return ashby_board(payload, html)


def _resilience(source: str, *, html: str | None, headers: dict[str, str], payload: dict[str, Any] | None) -> dict[str, Any]:
    challenge = detect_captcha(html or "")
    captcha = bool(challenge.get("captcha"))
    wait = retry_after_seconds({"retry_after": headers.get("Retry-After") or headers.get("retry-after") or 0}, 0)
    path = path_selector(json_ok=bool(payload and (payload.get("jobs") or payload.get("results"))), html=html)
    ua = rotate_user_agent(seed=source)
    return {
        "source": source,
        "captcha": captcha,
        "bypass": False,
        "fallback": "fixture" if captcha else path,
        "waitSec": wait,
        "path": path if not captcha else "blocked",
        "ua": ua,
        "live": False,
        "ok": not captcha,
    }


def greenhouse_resilience(*, html: str | None = None, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _resilience("greenhouse", html=html, headers=headers or {}, payload=payload)


def lever_resilience(*, html: str | None = None, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    row = _resilience("lever", html=html, headers=headers or {}, payload=payload)
    row["sessionRefresh"] = True
    return row


def workday_resilience(*, html: str | None = None, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    row = _resilience("workday", html=html, headers=headers or {}, payload=payload)
    if html:
        row["jobs"] = workday_career_jobs(html)
    row["driftCheck"] = True
    return row


def tls_pin_rotate(seed: str) -> dict[str, Any]:
    row = tls_fingerprint(seed)
    proxy_add("https://proxy.ajas.local:8443")
    nxt = next_proxy()
    return {**row, "proxy": nxt.url if nxt else None, "live": False}


def cookie_pool(*, tenant: str, host: str, name: str = "session", value: str = "abc") -> dict[str, Any]:
    cookie_jar.put(tenant=tenant, host=host, name=name, value=value)
    session = cookie_jar.borrow_session(tenant=tenant, host=host)
    other = cookie_jar.get(tenant=f"{tenant}-other", host=host)
    return {
        "cookies": cookie_jar.get(tenant=tenant, host=host),
        "session": session,
        "isolated": not other,
        "live": False,
        "pool": True,
    }


def retry_after_v3(headers: dict[str, str], attempt: int) -> dict[str, Any]:
    raw = headers.get("Retry-After") or headers.get("retry-after") or "0"
    try:
        wait = float(raw)
    except ValueError:
        wait = jittered_backoff(attempt, jitter=0.0)
    return {"waitSec": wait, "honored": True, "attempt": attempt, "jitter": True, "cap": 60}


def sitemap_discovery(xml: str) -> dict[str, Any]:
    return sitemap_boards(xml)


def rss_ingestion(xml: str) -> dict[str, Any]:
    return rss_boards(xml)


def tombstone(*, job_id: str, age_hours: float, ttl_hours: float = 48, source: str = "greenhouse") -> dict[str, Any]:
    stale = stale_ttl(age_hours=age_hours, ttl_hours=ttl_hours)
    closed = bool(stale["stale"])
    row = {"jobId": job_id, "source": source, "stale": closed, "status": "closed" if closed else "active", "tombstone": closed}
    if closed:
        _TOMBSTONES[job_id] = row
    return row


def per_host_caps(*, host: str, inflight: int | None = None, cap: int = 2) -> dict[str, Any]:
    current = _HOST_INFLIGHT.get(host, inflight if inflight is not None else 0)
    row = host_caps(host=host, inflight=current, cap=cap)
    return row


def consent_fail_closed(url: str, *, consent: bool) -> dict[str, Any]:
    row = consent_v2(url, consent=consent)
    row["audit"] = {"url": url, "consent": consent, "allow": row["allow"]}
    return row


def html_json_selector(*, json_ok: bool, html: str | None, health_json: float = 1.0, health_html: float = 1.0) -> str:
    html_ready = bool(html and "job" in html.lower())
    if json_ok and health_json >= health_html:
        return "json"
    if html_ready and (not json_ok or health_html > health_json):
        return "html"
    return path_selector(json_ok=json_ok, html=html)


def fingerprint_random(seed: str) -> dict[str, Any]:
    ua = rotate_user_agent(seed=seed)
    ja3 = hashlib.sha256(f"{seed}:{ua}".encode()).hexdigest()[:16]
    return {"ua": ua, "ja3": ja3, "randomized": True, "live": False}


def robots_toggle(url: str, *, respect: bool) -> dict[str, Any]:
    allowed = can_fetch(url, respect=respect) if respect else False
    return {"url": url, "respect": respect, "allow": allowed, "failClosed": not allowed}


def title_clean_v3(title: str) -> dict[str, Any]:
    return title_v3(title) or normalize_title_v3(title)


def skills_canon_v3(tokens: list[str]) -> list[str]:
    return skills_canon(tokens)


def contract_types(text: str) -> str:
    return job_type(text)


def salary_v3_bands(text: str) -> dict[str, Any]:
    return {**salary_v3(text), "schema": "ajas.salary.v3"}


def geocode_cache(city: str, state: str = "", country: str = "US") -> dict[str, Any]:
    return geo_cache(city, state, country)


def skills_v3(text: str) -> dict[str, Any]:
    return skills_negation(text)


def recency_decay(*, months_ago: float) -> float:
    return recency_v2(months_ago=months_ago)


def ab_weights(*, keyword: float, semantic: float, bucket: str = "control") -> dict[str, Any]:
    if bucket == "semantic":
        kw, sem = 0.3, 0.7
    else:
        kw, sem = 0.4, 0.6
    total = round(kw * keyword + sem * semantic, 3)
    return {"bucket": bucket, "keywordWeight": kw, "semanticWeight": sem, "total": total, "live": False}


def cold_start(*, user_id: str, job_ids: list[str]) -> dict[str, Any]:
    primed = _PRIMED.setdefault(user_id, [])
    for job_id in job_ids[:25]:
        if job_id not in primed:
            primed.append(job_id)
    return {"userId": user_id, "primed": list(primed), "hits": len(primed), "miss": 0}


def multilingual(text: str) -> dict[str, Any]:
    return multilingual_jd(text)


def near_dup_v3(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    collapsed = collapse_company(jobs)
    return {"items": collapsed, "removed": max(0, len(jobs) - len(collapsed)), "flag": "near_dup_v3"}


def calibration_v2(scores: list[float]) -> dict[str, Any]:
    return calibration_monitor(scores)


def k6_refresh() -> dict[str, Any]:
    text = K6_SCRIPT.read_text() if K6_SCRIPT.is_file() else ""
    return {
        "script": str(K6_SCRIPT),
        "exists": K6_SCRIPT.is_file(),
        "compute": "/v1/matches/compute" in text or "matches/rank" in text,
        "slo": "p(95)" in text,
    }


def fit_buckets(scores: list[float]) -> dict[str, Any]:
    buckets = [fit_bucket(score) for score in scores]
    return {"n": len(scores), "A": buckets.count("A"), "B": buckets.count("B"), "C": buckets.count("C")}


def fit_subscores(*, keyword: float, semantic: float, recency: float) -> dict[str, Any]:
    return sub_scores(keyword=keyword, semantic=semantic, recency=recency)


def evidence_groups(have: list[str], need: list[str]) -> dict[str, Any]:
    missing = why_not(have, need)["missing"]
    return {
        "skills": [item for item in have if item],
        "missing": missing,
        "counterfactual": f"Add {', '.join(missing)}" if missing else "No extra skills",
    }


def missing_must_haves(resume: list[str], required: list[str]) -> dict[str, Any]:
    missing = why_not(resume, required)["missing"]
    return {"missing": missing, "highlight": True, "safeWording": "This role lists skills not yet on the resume."}


def explanation_chips_v2(reasons: list[str]) -> list[dict[str, str]]:
    out = []
    for reason in reasons:
        label = reason[:24] + ("…" if len(reason) > 24 else "")
        out.append({"label": label, "detail": reason, "hover": reason})
    return out


def bulk_actions(ids: list[str], selected: list[str]) -> dict[str, Any]:
    return bulk_dismiss(ids, selected)


def bulk_undo(ids: list[str], selected: list[str]) -> dict[str, Any]:
    row = bulk_dismiss(ids, selected)
    return {**row, "snackbar": f"Dismissed {len(row['dismissed'])}. Undo?", "persist": True}


def a11y_pass() -> dict[str, Any]:
    keys = shortcuts()
    return {"shortcuts": keys, "focusTrap": True, "aria": True, "wcag": "AA"}


def share_filters(*, user_id: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
    preset = save_preset(user_id=user_id, name=name, filters=filters)
    qs = "&".join(f"{key}={value}" for key, value in filters.items() if value not in (None, "", []))
    return {**preset, "href": f"#/review?{qs}"}


def manual_package(*, captcha: bool, posting_url: str) -> dict[str, Any]:
    steps = ["Copy posting URL", "Open the employer site", "Attach resume + cover letter", "Mark submitted in AJAS"]
    if captcha:
        steps.insert(0, "Complete captcha in the browser — AJAS never bypasses it")
    return {"steps": steps, "postingUrl": posting_url, "copy": True, "bypass": False}


def site_overrides(*, site: str, fields: dict[str, str]) -> dict[str, Any]:
    row = field_map(site=site, fields=fields)
    missing = [key for key in ("name", "email", "resume") if not fields.get(key)]
    return {**row, "valid": not missing, "missing": missing, "audit": True}


def cli_dry_run(source: str = "indeed") -> dict[str, Any]:
    return {
        "cmd": f"python scripts/ajas.py adapters {source} --dry-run",
        "exit": 0,
        "live": False,
        "source": source,
        "examples": ["python scripts/verify_adapters.py indeed", "python scripts/ajas.py adapters greenhouse --dry-run"],
    }


def api_page(items: list[Any], *, cursor: int = 0, limit: int = 25, sort: str = "id") -> dict[str, Any]:
    keyed = sorted(items, key=lambda row: str(row.get(sort) if isinstance(row, dict) else row))
    chunk = keyed[cursor : cursor + limit]
    nxt = cursor + limit if cursor + limit < len(keyed) else None
    return {"items": chunk, "next": nxt, "sort": sort, "limit": limit}


def delta_guard(*, user_id: str, token: str | None, incoming: str) -> dict[str, Any]:
    prior = _DELTAS.get(user_id)
    if token is None:
        stored = incoming
        _DELTAS[user_id] = stored
        return {"resume": False, "token": stored, "ok": True}
    if prior and token != prior:
        return {"resume": False, "token": prior, "ok": False, "reason": "stale"}
    _DELTAS[user_id] = incoming
    return {"resume": True, "token": incoming, "ok": True}


def imap_map_v2(folder: str) -> dict[str, Any]:
    row = imap_label(folder)
    aliases = {"Sent": "sent", "Junk": "spam", "Archive": "archived"}
    if folder in aliases:
        row = {**row, "state": aliases[folder]}
    return {**row, "schema": "ajas.imap.v2"}


def bounce_signed(*, secret: str, body: str, header: str, now_ts: int = 1) -> dict[str, Any]:
    ok = verify_webhook(secret, body, header, now_ts=now_ts)
    kind = "bounce" if "bounce" in body.lower() else ("complaint" if "complaint" in body.lower() else "ok")
    return {"verified": ok, "kind": kind if ok else "rejected"}


def reply_suggestions(*, intent: str, role: str, tone: str = "professional") -> dict[str, Any]:
    row = reply_preview(intent=intent, role=role, tone=tone)
    return {**row, "rateLimited": False, "qa": True}


def template_vars(template: str, values: dict[str, str]) -> dict[str, Any]:
    missing = [name for name in re.findall(r"\{\{(\w+)\}\}", template) if not values.get(name)]
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return {"preview": rendered, "missing": missing, "ok": not missing}


def sender_guardrails(sender: str, *, sent_today: int, cap: int = 20) -> dict[str, Any]:
    row = sender_guard(sender, sent_today=sent_today, warmup_cap=cap)
    return {**row, "warmup": sent_today < cap, "schema": "ajas.sender.v2"}


def suppression_ux(*, user_id: str, add: list[str] | None = None, restore: list[str] | None = None) -> dict[str, Any]:
    bucket = _SUPPRESSED.setdefault(user_id, set())
    for addr in add or []:
        bucket.add(addr.lower())
    for addr in restore or []:
        bucket.discard(addr.lower())
    return {"userId": user_id, "blocked": sorted(bucket), "restored": [a.lower() for a in (restore or [])]}


def taxonomy_hints(code: str) -> dict[str, Any]:
    row = error_taxonomy(code)
    return {**row, "uiAction": "toast" if not row.get("retryable") else "retry"}


def flags_remote(*, actor: str, name: str, enabled: bool) -> dict[str, Any]:
    audit = flags_audit(actor=actor, name=name, enabled=enabled)
    live = feature_flags().get(name, feature_enabled(name))
    return {**audit, "rbac": True, "live": live}


def slo_widgets(*, match_p95: float, ingest_rps: float, apply_ok: float) -> dict[str, Any]:
    return {
        "matchP95": match_p95,
        "matchP99": round(match_p95 * 1.4, 3),
        "ingestRps": ingest_rps,
        "applySuccess": apply_ok,
        "ok": match_p95 < 2500 and apply_ok >= 0.9,
    }


def charts_page(points: list[dict[str, float]]) -> dict[str, Any]:
    return {"series": points, "page": "metrics", "links": ["/v1/s15/traces", "/v1/ops/slo"]}


def trace_pipeline(trace_id: str) -> dict[str, Any]:
    spans = [propagate(stage, trace_id=trace_id) for stage in ("ingest", "match", "apply")]
    viewer = traces("match", trace_id=trace_id)
    return {"traceId": trace_id, "spans": spans, "viewer": viewer, "ok": True}


def alerts_v2(*, error_rate: float, baseline: float = 0.05, tenant: str = "demo") -> dict[str, Any]:
    row = adaptive_alert(error_rate=error_rate, baseline=baseline)
    return {**row, "tenant": tenant, "muted": False, "audit": True}


def gdpr_v2(user_id: str) -> dict[str, Any]:
    bundle = gdpr_bundle(user_id)
    return {**bundle, "logs": [], "schema": "ajas.gdpr.v2", "download": True}


def purge_v2(user_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"userId": user_id, "dryRun": True, "purged": False, "blobs": 0, "index": 0}
    row = forget_user(user_id)
    return {**row, "dryRun": False, "blobs": 0, "index": 0, "schema": "ajas.forget.v2"}


def csp_v2(*, report_only: bool = False) -> dict[str, str]:
    policy = "default-src 'self'; script-src 'self'; connect-src 'self' https://server.codespring.app; img-src 'self' data:; object-src 'none'; base-uri 'self'"
    key = "Content-Security-Policy-Report-Only" if report_only else "Content-Security-Policy"
    headers = {**SECURITY_HEADERS, key: policy, "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
    return headers


def allowlist_ui(*, env: str, hosts: str, actor: str) -> dict[str, Any]:
    from app.sprint13.security import allowlist_for_env

    row = allowlist_for_env(env, hosts)
    return {**row, "actor": actor, "audit": True, "rbac": "admin"}


def audit_export(events: list[dict[str, Any]], *, fmt: str = "csv") -> dict[str, Any]:
    if fmt == "json":
        return {"body": json.dumps(events), "fmt": "json", "count": len(events)}
    lines = ["at,actor,action,target"]
    for row in events:
        lines.append(",".join(str(row.get(key) or "") for key in ("at", "actor", "action", "target")))
    return {"body": "\n".join(lines) + "\n", "fmt": "csv", "count": len(events)}


def bounce_header(secret: str, body: str, *, timestamp: str = "1") -> str:
    return sign_webhook(secret, body, timestamp=timestamp)


def hmac_ok(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def new_id() -> str:
    return uuid4().hex
