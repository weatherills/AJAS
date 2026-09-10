"""Map stored postings into the Job Feed HTTP shape (Frontend PRD)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.job_sources.models import JobPostingCanonical, JobPostingRaw, SourceTenant
from app.job_sources.store import JobSourceStore


def parse_sources_query(raw: str | None, url: str = "") -> list[str] | None:
    """Omitted ``sources`` defaults later; an explicit blank (or ``none``) matches nothing.

    Azure Functions drops empty query values from ``req.params``, so callers may
    pass the request URL as a fallback when ``raw`` is ``None``.
    """
    if raw is None and url:
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        if "sources" in query:
            raw = ",".join(query.get("sources") or [])
    if raw is None:
        return None
    return [
        part.strip()
        for part in raw.split(",")
        if part.strip() and part.strip().lower() != "none"
    ]


def source_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or url
    except ValueError:
        return url
    return host.removeprefix("www.")


def seed_demo_feed(store: JobSourceStore) -> None:
    """Local empty-Cosmos sample so the feed is usable before a live crawl."""
    if store.list_canonical():
        return
    greenhouse = store.upsert_tenant(
        "greenhouse",
        "acme",
        config={"board_token": "acme", "company": "Acme", "namespace": "acme"},
    )
    lever = store.upsert_tenant(
        "lever",
        "acme",
        config={"site": "acme", "company": "Acme", "namespace": "acme"},
    )
    samples = [
        (greenhouse, "1", "Staff Engineer", "Remote", "Acme", "greenhouse"),
        (greenhouse, "2", "Platform Engineer", "New York, NY", "Acme", "greenhouse"),
        (lever, "lev-1", "Staff Engineer", "Remote", "Acme", "lever"),
        (lever, "lev-2", "Data Analyst", "Austin, TX", "Globex", "lever"),
        (greenhouse, "3", "Frontend Engineer", "London", "Initech", "greenhouse"),
        (lever, "lev-3", "Backend Engineer", "Remote", "Hooli", "lever"),
    ]
    skills = {
        "Staff Engineer": "python azure cosmos kubernetes terraform matching crawlers ingestion",
        "Platform Engineer": "python azure functions kubernetes terraform matching",
        "Backend Engineer": "python azure cosmos functions apis matching",
        "Frontend Engineer": "react typescript css design systems",
        "Data Analyst": "sql tableau spreadsheets forecasting",
    }
    for tenant, posting_id, title, location, company, source in samples:
        apply_url = (
            f"https://boards.greenhouse.io/{company.lower()}/jobs/{posting_id}"
            if source == "greenhouse"
            else f"https://jobs.lever.co/{company.lower()}/{posting_id}"
        )
        skill_line = skills.get(title, "general")
        closer = {
            "Staff Engineer": "Build public job ingestion, matching, and review tools.",
            "Platform Engineer": "Ship Azure services, crawlers, and matching pipelines.",
            "Backend Engineer": "Design APIs, Cosmos persistence, and matching workers.",
            "Frontend Engineer": "Ship React interfaces, design systems, and CSS.",
            "Data Analyst": "Model spreadsheets, SQL, and forecasting dashboards.",
        }.get(title, "")
        body = (
            f"Title: {title}\nCompany: {company}\nSkills: {skill_line}\n"
            f"{title} at {company} in {location}. {closer}"
        )
        store.ingest_raw(
            tenant.id,
            source_posting_id=posting_id,
            title=title,
            location=location,
            employment_type="Full-time",
            company=company,
            apply_url=apply_url,
            body=body,
            payload=body,
            namespace="acme" if company == "Acme" else company.lower(),
        )


def _tenant_source(tenant: SourceTenant) -> str:
    return tenant.source_id if tenant.source_id in {"greenhouse", "lever"} else "greenhouse"


def feed_cards(store: JobSourceStore) -> list[dict]:
    tenants = {item.id: item for item in store.list_tenants()}
    canonical_by_id = {item.id: item for item in store.list_canonical()}
    raw_by_id: dict[str, JobPostingRaw] = {}
    for tenant in tenants.values():
        for raw in store.list_raw(tenant.id, current_only=True):
            raw_by_id[raw.id] = raw
    by_canonical: dict[str, list[JobPostingRaw]] = {}
    for link in store.list_links():
        raw = raw_by_id.get(link.raw_id)
        if raw is None:
            continue
        by_canonical.setdefault(link.canonical_id, []).append(raw)
    cards: list[dict] = []
    for canonical_id, raws in by_canonical.items():
        canonical = canonical_by_id.get(canonical_id)
        if canonical is None or not canonical.is_active:
            continue
        refs = []
        for raw in raws:
            tenant = tenants.get(raw.source_tenant_id)
            source = _tenant_source(tenant) if tenant else "greenhouse"
            url = raw.apply_url or ""
            refs.append(
                {
                    "source": source,
                    "sourceUrl": url,
                    "postedAt": raw.seen_first_at,
                    "domain": source_domain(url) if url else source,
                }
            )
        refs.sort(key=lambda item: item["postedAt"] or "", reverse=True)
        primary = refs[0] if refs else {"source": "greenhouse"}
        newest = max(raws, key=lambda item: item.updated_at)
        company = next((item.company for item in raws if item.company), "")
        apply_url = next((item.apply_url for item in raws if item.apply_url), "")
        cards.append(
            {
                "id": canonical.id,
                "canonicalKey": canonical.canonical_key,
                "title": canonical.title,
                "company": company,
                "location": canonical.location,
                "employmentType": canonical.employment_type or "Full-time",
                "snippet": (newest.body or "")[:160],
                "applyUrl": apply_url,
                "updatedAt": newest.updated_at,
                "isNew": False,
                "sources": refs,
                "primarySource": primary["source"],
                "description": newest.body or "",
            }
        )
    cards.sort(key=lambda item: item["updatedAt"], reverse=True)
    return cards


def filter_cards(
    cards: list[dict],
    *,
    sources: list[str] | None,
    q: str,
    location: str,
    status: str,
    since: str | None,
) -> list[dict]:
    wanted = {"greenhouse", "lever"} if sources is None else set(sources)
    query = (q or "").strip().lower()
    loc = (location or "").strip().lower()
    out: list[dict] = []
    for card in cards:
        card_sources = {item["source"] for item in card["sources"]}
        if not (card_sources & wanted):
            continue
        if query:
            blob = f"{card['title']} {card['company']} {card['location']}".lower()
            if query not in blob:
                continue
        if loc and loc not in (card["location"] or "").lower():
            continue
        is_new = bool(since and card["updatedAt"] > since)
        if status == "new" and not is_new:
            continue
        item = dict(card)
        item["isNew"] = is_new
        out.append(item)
    return out
