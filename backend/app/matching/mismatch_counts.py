"""Count top skill mismatches between a resume and a job."""

from __future__ import annotations

from collections import Counter
from app.matching.scoring import tokenize


def mismatch_counts(resume_text: str, job_text: str, *, limit: int = 8) -> dict[str, object]:
    resume = Counter(tokenize(resume_text))
    job = Counter(tokenize(job_text))
    missing = []
    extra = []
    for term, count in job.most_common():
        have = resume.get(term, 0)
        if have < count:
            missing.append({"term": term, "job": count, "resume": have, "gap": count - have})
    for term, count in resume.most_common():
        if term not in job:
            extra.append({"term": term, "resume": count})
    return {"missing": missing[:limit], "extra": extra[:limit]}
