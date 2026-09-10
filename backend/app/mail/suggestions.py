"""Reply suggestion drafts (Azure OpenAI when configured, canned otherwise)."""

from __future__ import annotations

from app.mail.models import EmailMessage, EmailThread


def _clip(text: str, limit: int = 1800) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit]


def canned_suggestions(thread: EmailThread, messages: list[EmailMessage], *, tone: str | None, notes: str | None) -> list[dict]:
    inbound = next((item for item in reversed(messages) if item.is_incoming), messages[-1] if messages else None)
    recruiter = (inbound.from_name if inbound else "there").split(" ")[0] or "there"
    role = thread.job_title or "the role"
    company = thread.job_company or "your team"
    extra = f" {notes.strip()}" if notes else ""
    wanted = (tone or "professional").lower()
    drafts = [
        {
            "text": (
                f"Hi {recruiter},\n\nThank you for your note about {role} at {company}. "
                f"I'm interested and can make time this week to talk through next steps.{extra}\n\nBest regards"
            ),
            "tone": "professional",
            "rationale": "Acknowledges the recruiter and offers availability.",
        },
        {
            "text": (
                f"Hi {recruiter},\n\nThanks — I'm keen on {role} at {company} and can jump on a call. "
                f"What times work for you?{extra}\n\nThanks"
            ),
            "tone": "concise",
            "rationale": "Short reply that asks for scheduling times.",
        },
        {
            "text": (
                f"Hi {recruiter},\n\nReally appreciate you reaching out about {role} at {company}. "
                f"I'd love to learn more and share how I can help.{extra}\n\nWarmly"
            ),
            "tone": "warm",
            "rationale": "Friendly tone while staying on the job context.",
        },
    ]
    if wanted in {"professional", "concise", "warm"}:
        drafts.sort(key=lambda item: 0 if item["tone"] == wanted else 1)
    for item in drafts:
        item["text"] = _clip(item["text"], 2000)
    return drafts[:3]


def generate_suggestions(thread: EmailThread, messages: list[EmailMessage], *, tone: str | None, notes: str | None) -> list[dict]:
    from app.config import get_settings

    settings = get_settings()
    if not (settings.azure_openai_endpoint or "").strip() or not (settings.azure_openai_api_key or "").strip():
        return canned_suggestions(thread, messages, tone=tone, notes=notes)
    try:
        from app.ai.openai_client import get_openai_client

        client = get_openai_client()
        history = "\n".join(
            f"{'Recruiter' if item.is_incoming else 'Me'}: {_clip(item.body_text, 400)}" for item in messages[-10:]
        )
        prompt = (
            f"Write three short job-application email replies. Job: {thread.job_title} at {thread.job_company}. "
            f"Tone hint: {tone or 'professional'}. Notes: {notes or 'none'}.\n\nThread:\n{history}\n"
            "Return three replies labeled professional, concise, and warm."
        )
        response = client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
        )
        text = (response.choices[0].message.content or "").strip()
        if text:
            chunks = [part.strip() for part in text.split("\n\n") if part.strip()][:3]
            tones = ["professional", "concise", "warm"]
            if len(chunks) == 3:
                return [
                    {"text": _clip(chunk, 2000), "tone": tones[idx], "rationale": "Generated from recent thread context."}
                    for idx, chunk in enumerate(chunks)
                ]
    except Exception:
        pass
    return canned_suggestions(thread, messages, tone=tone, notes=notes)
