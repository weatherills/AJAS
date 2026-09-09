"""Process-wide ReviewService used by HTTP and queue triggers."""

from __future__ import annotations

from app.review.service import ReviewService

DEMO_USER = "local-user"

_service: ReviewService | None = None


def _seed_demo_matches(store) -> None:
    """Load a small local queue so Phase 1 UI works without Cosmos."""
    if store.list_matches(DEMO_USER):
        return
    samples = [
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
    ]
    for sample in samples:
        store.create_match(DEMO_USER, **sample)
    decided = store.create_match(
        DEMO_USER,
        job_id="job-history",
        resume_id="resume-1",
        job_title="Platform SRE",
        company="Umbrella",
        location="Remote",
        ai_score=81.0,
        suggestion="approve",
        why="On-call and Kubernetes experience lines up with the posting.",
        summary="Strong SRE overlap; previously approved for tracking.",
        highlights_json=["Kubernetes", "on-call"],
        source="ai",
    )
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


def set_service(service: ReviewService | None) -> None:
    global _service
    _service = service
