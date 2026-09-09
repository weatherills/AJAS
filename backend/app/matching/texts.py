"""Load resume/job text by id. Default is not-found on this isolated slice."""

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
