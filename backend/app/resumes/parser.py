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
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("skills:"):
                skills.extend(part.strip() for part in stripped.split(":", 1)[1].split(",") if part.strip())
        payload: dict[str, Any] = {"skills": skills[:20]}
        if not skills and text.strip():
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
