"""Load resume/job text by id from Resume Management and Job Source stores."""

from __future__ import annotations

from typing import Protocol

from app.matching.errors import MatchingNotFoundError


class TextLoader(Protocol):
    def load_resume(self, user_id: str, resume_id: str) -> str: ...

    def load_job(self, user_id: str, job_id: str) -> str: ...


class NotFoundTextLoader:
    def load_resume(self, user_id: str, resume_id: str) -> str:
        raise MatchingNotFoundError(resume_id)

    def load_job(self, user_id: str, job_id: str) -> str:
        raise MatchingNotFoundError(job_id)


class StackedTextLoader:
    """Resolve resume/job ids against the stacked Resume and Job Source services."""

    def load_resume(self, user_id: str, resume_id: str) -> str:
        from app.resumes.errors import ResumeNotFoundError
        from app.resumes.runtime import get_service as get_resume_service

        try:
            rec = get_resume_service().get(user_id, resume_id)
        except ResumeNotFoundError as exc:
            raise MatchingNotFoundError(resume_id) from exc
        parts: list[str] = []
        if rec.contact:
            parts.extend([p for p in (rec.contact.full_name, rec.contact.email) if p])
        parts.extend(skill.name for skill in rec.skills if skill.name)
        for exp in rec.experiences:
            parts.extend([p for p in (exp.title, exp.company, exp.description) if p])
        haystack = " ".join(parts)
        text = haystack or rec.text_preview or ""
        if not text.strip():
            raise MatchingNotFoundError(resume_id)
        return text

    def load_job(self, user_id: str, job_id: str) -> str:
        from app.job_sources.errors import JobSourceNotFoundError
        from app.job_sources.runtime import get_service as get_job_service

        try:
            rec = get_job_service().get_feed_job(job_id)
        except JobSourceNotFoundError as exc:
            raise MatchingNotFoundError(job_id) from exc
        text = " ".join(
            p
            for p in (
                rec.get("title"),
                rec.get("company"),
                rec.get("location"),
                rec.get("employmentType"),
                rec.get("description") or rec.get("snippet"),
            )
            if p
        )
        if not text.strip():
            raise MatchingNotFoundError(job_id)
        return text


class MemoryTextLoader:
    def __init__(self) -> None:
        self.resumes: dict[tuple[str, str], str] = {}
        self.jobs: dict[tuple[str, str], str] = {}

    def put_resume(self, user_id: str, resume_id: str, text: str) -> None:
        self.resumes[(user_id, resume_id)] = text

    def put_job(self, user_id: str, job_id: str, text: str) -> None:
        self.jobs[(user_id, job_id)] = text

    def load_resume(self, user_id: str, resume_id: str) -> str:
        try:
            return self.resumes[(user_id, resume_id)]
        except KeyError as exc:
            raise MatchingNotFoundError(resume_id) from exc

    def load_job(self, user_id: str, job_id: str) -> str:
        try:
            return self.jobs[(user_id, job_id)]
        except KeyError as exc:
            raise MatchingNotFoundError(job_id) from exc
