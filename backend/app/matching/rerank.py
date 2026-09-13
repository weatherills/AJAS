"""Second-stage cross-encoder rerank scaffold (token overlap stand-in)."""

from __future__ import annotations

from app.matching.scoring import tokenize


def cross_encoder_score(resume_text: str, job_text: str) -> float:
    resume = set(tokenize(resume_text))
    job = set(tokenize(job_text))
    if not resume or not job:
        return 0.0
    overlap = len(resume & job) / len(resume | job)
    return round(100.0 * overlap, 1)


def rerank(pairs: list[dict], *, top_n: int | None = None) -> list[dict]:
    scored = []
    for row in pairs:
        score = cross_encoder_score(str(row.get("resume") or ""), str(row.get("job") or row.get("body") or ""))
        scored.append({**row, "rerank": score})
    scored.sort(key=lambda item: float(item["rerank"]), reverse=True)
    return scored[: top_n or len(scored)]
