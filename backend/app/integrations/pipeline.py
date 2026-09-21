"""In-memory E2E: LinkedIn ingest → match/review → Easy Apply receipt."""

from __future__ import annotations

from typing import Any

from app.integrations.easy_apply import submit as easy_apply_submit
from app.integrations.ingest import linkedin_ingest
from app.matching.boosts import fit_bucket
from app.matching.evidence import evidence_sentences
from app.matching.keys import overall_score_pct
from app.matching.scoring import keyword_score
from app.review.constants import DECISIONS


def _score(resume_text: str, job: dict[str, Any]) -> dict[str, Any]:
    job_text = "\n".join(
        part
        for part in (
            f"Title: {job.get('title') or ''}",
            f"Company: {job.get('company') or ''}",
            f"Location: {job.get('location') or ''}",
            str(job.get("description") or ""),
        )
        if part
    )
    keyword = keyword_score(resume_text, job_text)
    value = overall_score_pct(keyword, keyword)
    bucket = fit_bucket(value)
    return {
        "score": value,
        "bucket": bucket,
        "evidence": evidence_sentences(resume_text, job_text, limit=3),
        "jobId": job.get("id"),
        "raw": {"keyword": keyword, "score": value},
    }


def _decide(score: float, decision: str | None) -> dict[str, Any]:
    suggestion = "approve" if score >= 75 else "reject" if score < 50 else "review"
    chosen = decision if decision in DECISIONS else ("approve" if suggestion != "reject" else "reject")
    return {"decision": chosen, "suggestion": suggestion, "status": "APPROVED" if chosen == "approve" else "REJECTED"}


def run_linkedin_e2e(
    payload: Any,
    *,
    resume_text: str,
    profile: dict[str, str],
    attachments: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
    decision: str = "approve",
    search: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ingested = linkedin_ingest(payload, search=search)
    jobs = ingested.get("jobs") or []
    matches = [_score(resume_text, job) for job in jobs]
    reviews = [_decide(float(match["score"]), decision) for match in matches]
    receipts: list[dict[str, Any]] = []
    for job, review in zip(jobs, reviews, strict=False):
        if review["decision"] != "approve":
            continue
        if job.get("applyMethod") != "easy_apply":
            continue
        result = easy_apply_submit(
            job=job,
            profile=profile,
            questions=questions
            or [
                {"key": "work_authorization", "prompt": "Are you authorized to work?"},
                {"key": "years_experience", "prompt": "Years of experience?"},
            ],
            attachments=attachments
            or [
                {
                    "kind": "resume",
                    "name": "resume.pdf",
                    "contentType": "application/pdf",
                    "data": b"%PDF-1.4 cv",
                }
            ],
        )
        receipts.append(result)
    return {
        "ingest": ingested,
        "jobs": jobs,
        "matches": matches,
        "reviews": reviews,
        "applies": receipts,
        "ok": bool(jobs) and any(item.get("status") == "submitted" for item in receipts),
    }
