"""Job linking rules for inbound mail (Backend PRD)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.mail.models import EmailMessage, EmailThread

TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class JobHint:
    id: str
    title: str
    company: str
    contacts: list[str]
    tokens: list[str]


@dataclass
class LinkDecision:
    job: JobHint | None
    source: str | None
    confidence: int
    ambiguous: bool = False
    score: float = 0.0


def _norm(value: str) -> str:
    return " ".join((value or "").lower().split())


def _tokens(value: str) -> set[str]:
    return {item for item in TOKEN_RE.findall(_norm(value)) if len(item) > 1}


def score_job(message: EmailMessage, job: JobHint) -> float:
    blob = " ".join(
        [
            message.subject,
            message.from_address,
            message.from_name,
            " ".join(message.to_addresses),
            message.body_text[:400],
        ]
    )
    hay = _tokens(blob)
    needles = _tokens(" ".join([job.title, job.company, *job.tokens, *job.contacts]))
    if not needles:
        return 0.0
    overlap = hay & needles
    return min(1.0, len(overlap) / max(3, min(len(needles), 8)))


def decide_link(
    message: EmailMessage,
    *,
    existing_thread: EmailThread | None,
    referenced_thread: EmailThread | None,
    jobs: list[JobHint],
    auto_threshold: float,
) -> LinkDecision:
    if existing_thread and (existing_thread.job_posting_id or existing_thread.application_id):
        job = next((item for item in jobs if item.id == existing_thread.job_posting_id), None)
        return LinkDecision(job=job, source="rule", confidence=100, score=1.0)
    if referenced_thread and (referenced_thread.job_posting_id or referenced_thread.application_id):
        job = next((item for item in jobs if item.id == referenced_thread.job_posting_id), None)
        return LinkDecision(job=job, source="rule", confidence=95, score=0.95)

    contact_hits: list[JobHint] = []
    from_blob = _norm(f"{message.from_address} {message.from_name}")
    for job in jobs:
        if any(_norm(contact) and _norm(contact) in from_blob for contact in job.contacts):
            contact_hits.append(job)
        elif job.company and _norm(job.company) in from_blob:
            contact_hits.append(job)
    if len(contact_hits) == 1:
        return LinkDecision(job=contact_hits[0], source="rule", confidence=88, score=0.88)
    if len(contact_hits) > 1:
        return LinkDecision(job=None, source=None, confidence=0, ambiguous=True, score=0.4)

    subject = _norm(message.subject)
    token_hits: list[JobHint] = []
    for job in jobs:
        title = _norm(job.title)
        company = _norm(job.company)
        job_ref = next((token for token in job.tokens if token.lower().startswith("job")), "")
        if title and title in subject and company and company in subject:
            token_hits.append(job)
        elif job_ref and job_ref.lower() in subject:
            token_hits.append(job)
    if len(token_hits) == 1:
        return LinkDecision(job=token_hits[0], source="rule", confidence=80, score=0.8)
    if len(token_hits) > 1:
        return LinkDecision(job=None, source=None, confidence=0, ambiguous=True, score=0.45)

    ranked = sorted(((score_job(message, job), job) for job in jobs), key=lambda item: item[0], reverse=True)
    if not ranked:
        return LinkDecision(job=None, source=None, confidence=0, score=0.0)
    best_score, best_job = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score >= auto_threshold and (best_score - second) >= 0.08:
        return LinkDecision(
            job=best_job,
            source="auto",
            confidence=int(round(best_score * 100)),
            score=best_score,
        )
    if best_score >= 0.4 and abs(best_score - second) < 0.08:
        return LinkDecision(job=None, source=None, confidence=0, ambiguous=True, score=best_score)
    return LinkDecision(job=None, source=None, confidence=0, score=best_score)
