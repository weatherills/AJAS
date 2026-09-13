"""Turn extracted resume text into a structured snapshot."""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.config import get_settings
from app.resumes.mapping import snapshot_from_parser
from app.resumes.models import StructuredResume


class ResumeParser(Protocol):
    def parse(self, *, resume_id: str, text: str) -> StructuredResume: ...


class HeuristicResumeParser:
    """Offline fallback used in tests and when Azure OpenAI is not configured."""

    def parse(self, *, resume_id: str, text: str) -> StructuredResume:
        skills: list[str] = []
        experience: list[dict[str, Any]] = []
        education: list[dict[str, Any]] = []
        certs: list[str] = []
        current = ""
        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("skills:"):
                skills.extend(part.strip() for part in stripped.split(":", 1)[1].split(",") if part.strip())
                current = "skills"
                continue
            if lower.startswith("experience:"):
                current = "experience"
                rest = stripped.split(":", 1)[1].strip()
                if rest:
                    experience.append({"title": rest, "description": rest})
                continue
            if lower.startswith("education:"):
                current = "education"
                rest = stripped.split(":", 1)[1].strip()
                if rest:
                    education.append({"institution": rest, "degree": rest})
                continue
            if lower.startswith("certifications:") or lower.startswith("certs:"):
                current = "certs"
                certs.extend(part.strip() for part in stripped.split(":", 1)[1].split(",") if part.strip())
                continue
            if current == "experience" and stripped:
                experience.append({"title": stripped, "description": stripped})
            elif current == "education" and stripped:
                education.append({"institution": stripped, "degree": stripped})
            elif current == "certs" and stripped:
                certs.extend(part.strip() for part in stripped.split(",") if part.strip())
            elif current == "skills" and stripped and ":" not in stripped:
                skills.extend(part.strip() for part in stripped.split(",") if part.strip())
        payload: dict[str, Any] = {"skills": (skills + certs)[:20]}
        if experience:
            payload["experience"] = experience[:8]
        if education:
            payload["education"] = education[:6]
        if not skills and not experience and not education and text.strip():
            payload["skills"] = [text.strip().split()[0][:100]]
        return snapshot_from_parser(resume_id, payload)


class AzureOpenAIResumeParser:
    def parse(self, *, resume_id: str, text: str) -> StructuredResume:
        from app.ai.openai_client import get_openai_client

        settings = get_settings()
        client = get_openai_client()
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract resume fields as JSON with keys: "
                        "contact{fullName,email,phone,location}, skills[], "
                        "experience[{title,company,location,startDate,endDate,isCurrent,description}], "
                        "education[{institution,degree,field,startDate,endDate,isCurrent,notes}]. "
                        "Dates must be YYYY-MM or YYYY-MM-DD. Do not include secrets or extra keys."
                    ),
                },
                {"role": "user", "content": text[:20000]},
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return snapshot_from_parser(resume_id, payload)


def default_parser() -> ResumeParser:
    settings = get_settings()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        return AzureOpenAIResumeParser()
    return HeuristicResumeParser()
