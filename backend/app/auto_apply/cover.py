"""Optional cover-letter generation (Azure OpenAI when configured)."""

from __future__ import annotations

from typing import Any

from app.auto_apply.models import AutoApplyAttempt

MAX_COVER_CHARS = 4000
COVER_MAX_TOKENS = 400


def canned_cover_letter(attempt: AutoApplyAttempt, profile: dict[str, str]) -> str:
    name = profile.get("full_name") or profile.get("name") or "the candidate"
    role = attempt.job_id or "this role"
    posting = attempt.posting_url or f"the {attempt.vendor} posting"
    return (
        f"Dear hiring team,\n\n"
        f"I am writing to apply for {role} ({posting}). "
        f"My background matches the posting, and I would welcome the chance to contribute.\n\n"
        f"Sincerely,\n{name}\n"
    )


def generate_cover_letter(attempt: AutoApplyAttempt, profile: dict[str, str]) -> str:
    """Return a tailored letter. OpenAI failures fall back to the canned template."""
    from app.config import get_settings

    settings = get_settings()
    if not (settings.azure_openai_endpoint or "").strip() or not (settings.azure_openai_api_key or "").strip():
        return canned_cover_letter(attempt, profile)
    try:
        from app.ai.openai_client import get_openai_client

        client = get_openai_client()
        name = profile.get("full_name") or "the candidate"
        prompt = (
            "Write a short tailored cover letter (under 1000 tokens). "
            f"Candidate: {name}, email {profile.get('email') or 'unknown'}. "
            f"Vendor: {attempt.vendor}. Job id: {attempt.job_id or 'unknown'}. "
            f"Posting URL: {attempt.posting_url or 'unknown'}. "
            "Do not invent employers or metrics. Sign with the candidate name."
        )
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=COVER_MAX_TOKENS,
        )
        text = (response.choices[0].message.content or "").strip()
        if text:
            return text[:MAX_COVER_CHARS]
    except Exception:
        pass
    return canned_cover_letter(attempt, profile)


def cover_from_mode(mode: str, attempt: AutoApplyAttempt, profile: dict[str, str], body: dict[str, Any]) -> str | None:
    if mode == "generate":
        return generate_cover_letter(attempt, profile)
    if mode == "upload":
        uploaded = body.get("cover_letter_text")
        if isinstance(uploaded, str) and uploaded.strip():
            return uploaded.strip()[:MAX_COVER_CHARS]
    return None
