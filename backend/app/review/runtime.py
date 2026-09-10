"""Process-wide ReviewService used by HTTP and queue triggers."""

from __future__ import annotations

from app.review.service import ReviewService

DEMO_USER = "local-user"

_service: ReviewService | None = None


def _feed_cards() -> list[dict]:
    try:
        from app.job_sources.feed import feed_cards, seed_demo_feed
        from app.job_sources.store import get_job_source_store

        store = get_job_source_store()
        seed_demo_feed(store)
        return feed_cards(store)
    except Exception:
        return []


def _pick_card(cards: list[dict], title: str, company: str | None = None) -> dict | None:
    needle = title.lower()
    wanted = (company or "").lower()
    for card in cards:
        if needle not in (card.get("title") or "").lower():
            continue
        if wanted and (card.get("company") or "").lower() != wanted:
            continue
        return card
    return None


def _sample_from_card(card: dict | None, fallback: dict) -> dict:
    if not card:
        return fallback
    merged = dict(fallback)
    merged["job_id"] = card["id"]
    merged["job_title"] = card.get("title") or fallback["job_title"]
    merged["company"] = card.get("company") or fallback["company"]
    merged["location"] = card.get("location") or fallback["location"]
    return merged


def _seed_demo_matches(store) -> None:
    """Load a small local queue so Phase 1 UI works without Cosmos.

    Job ids come from the demo job feed when it is available so Review, Email,
    and the Jobs drawer all point at the same postings.
    """
    if store.list_matches(DEMO_USER):
        return
    cards = _feed_cards()
    samples = [
        _sample_from_card(
            _pick_card(cards, "staff engineer", "Acme"),
            {
                "job_id": "job-staff",
                "resume_id": "resume-1",
                "job_title": "Staff Platform Engineer",
                "company": "Acme",
                "location": "Remote",
                "ai_score": 88.0,
                "suggestion": "approve",
                "why": "The resume matches core backend and platform keywords in this posting.",
                "summary": "Strong overlap on platform work, Python, and Azure.",
                "highlights_json": ["Python services", "Azure", "Kubernetes", "Staff-level scope"],
                "source": "ai",
            },
        ),
        _sample_from_card(
            _pick_card(cards, "data analyst"),
            {
                "job_id": "job-data",
                "resume_id": "resume-1",
                "job_title": "Data Analyst",
                "company": "Globex",
                "location": "Austin",
                "ai_score": 41.0,
                "suggestion": "reject",
                "why": "This role is analytics-heavy; the resume is stronger on platform engineering.",
                "summary": "Limited overlap on SQL reporting and BI tools.",
                "highlights_json": ["SQL", "dashboards"],
                "source": "ai",
            },
        ),
        _sample_from_card(
            _pick_card(cards, "backend engineer", "Hooli") or _pick_card(cards, "backend engineer"),
            {
                "job_id": "job-saved",
                "resume_id": "resume-1",
                "job_title": "Senior Backend Engineer",
                "company": "Initech",
                "location": "New York",
                "ai_score": 76.0,
                "suggestion": "review",
                "why": "Solid API experience; missing some of the stated Java requirement.",
                "summary": "Good backend match with a skills gap on Java.",
                "highlights_json": ["APIs", "distributed systems"],
                "source": "saved",
            },
        ),
    ]
    for sample in samples:
        store.create_match(DEMO_USER, **sample)
    history = _sample_from_card(
        _pick_card(cards, "platform engineer"),
        {
            "job_id": "job-history",
            "resume_id": "resume-1",
            "job_title": "Platform SRE",
            "company": "Umbrella",
            "location": "Remote",
            "ai_score": 81.0,
            "suggestion": "approve",
            "why": "On-call and Kubernetes experience lines up with the posting.",
            "summary": "Strong SRE overlap; previously approved for tracking.",
            "highlights_json": ["Kubernetes", "on-call"],
            "source": "ai",
        },
    )
    decided = store.create_match(DEMO_USER, **history)
    store.decide(
        DEMO_USER,
        decided.id,
        "approve",
        comment="Approved last week after reading the on-call expectations.",
        etag=decided.etag,
        idempotency_key="seed-history-1",
    )


def get_service() -> ReviewService:
    global _service
    if _service is None:
        from app.review.blobs import default_blobs
        from app.review.queues import default_queue
        from app.review.store import get_review_store

        store = get_review_store()
        _seed_demo_matches(store)
        _service = ReviewService(
            store=store,
            queue=default_queue(),
            blobs=default_blobs(),
        )
    return _service


def try_get_service() -> ReviewService | None:
    return _service


def set_service(service: ReviewService | None) -> None:
    global _service
    _service = service
