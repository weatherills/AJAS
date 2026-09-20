"""Blob container names, key conventions, metadata tags, and lifecycle rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RESUMES = "resumes"
JOB_RAW = "job-raw"
REVIEW_ARTIFACTS = "review-artifacts"
MAIL_ATTACHMENTS = "mail-attachments"
AUTO_APPLY = "auto-apply-artifacts"
COVER_LETTERS = "cover-letters"
MATCH_EXPLANATIONS = "match-explanations"


@dataclass(frozen=True)
class BlobContainer:
    name: str
    purpose: str
    key_pattern: str
    metadata_tags: tuple[str, ...]
    cool_after_days: int | None = None
    delete_after_days: int | None = None
    public_access: str = "None"


BLOB_CONTAINERS: tuple[BlobContainer, ...] = (
    BlobContainer(
        name=RESUMES,
        purpose="Original resume PDFs/DOCX plus generated previews",
        key_pattern="{user_id}/{resume_id}/{filename}",
        metadata_tags=("user_id", "resume_id", "checksum_sha256", "mime_type"),
        delete_after_days=730,
    ),
    BlobContainer(
        name=JOB_RAW,
        purpose="Raw Greenhouse/Lever posting payloads",
        key_pattern="{source_tenant_id}/{source_posting_id}/{fetched_at}.json",
        metadata_tags=("source", "source_tenant_id", "source_posting_id", "response_hash"),
        cool_after_days=30,
        delete_after_days=90,
    ),
    BlobContainer(
        name=REVIEW_ARTIFACTS,
        purpose="Match summaries and highlight JSON for the Review UI",
        key_pattern="{user_id}/{match_id}/{artifact}",
        metadata_tags=("user_id", "match_id", "kind"),
        cool_after_days=90,
        delete_after_days=365,
    ),
    BlobContainer(
        name=MAIL_ATTACHMENTS,
        purpose="Email attachment bytes (inline + regular)",
        key_pattern="{email_account_id}/{message_id}/{attachment_id}",
        metadata_tags=("email_account_id", "message_id", "content_id", "is_inline"),
        delete_after_days=180,
    ),
    BlobContainer(
        name=AUTO_APPLY,
        purpose="Frozen apply packages, filled-form snapshots, screenshots",
        key_pattern="{user_id}/{auto_apply_id}/{kind}/{filename}",
        metadata_tags=("user_id", "auto_apply_id", "kind", "vendor"),
        delete_after_days=547,
    ),
    BlobContainer(
        name=COVER_LETTERS,
        purpose="AI or uploaded cover letters referenced by apply_packages",
        key_pattern="{user_id}/{cover_letter_id}.{ext}",
        metadata_tags=("user_id", "source"),
        delete_after_days=547,
    ),
    BlobContainer(
        name=MATCH_EXPLANATIONS,
        purpose="Overflow feature vectors and long match explanations",
        key_pattern="{user_id}/{match_id}/explanation.json",
        metadata_tags=("user_id", "match_id", "model_version_id"),
        delete_after_days=547,
    ),
)


def blob_container_names() -> tuple[str, ...]:
    return tuple(item.name for item in BLOB_CONTAINERS)


def resume_key(user_id: str, resume_id: str, filename: str) -> str:
    return f"{user_id}/{resume_id}/{filename}"


def job_raw_key(source_tenant_id: str, source_posting_id: str, fetched_at: str) -> str:
    stamp = fetched_at.replace(":", "").replace("+", "")
    return f"{source_tenant_id}/{source_posting_id}/{stamp}.json"


def review_artifact_key(user_id: str, match_id: str, artifact: str) -> str:
    return f"{user_id}/{match_id}/{artifact}"


def mail_attachment_key(email_account_id: str, message_id: str, attachment_id: str) -> str:
    return f"{email_account_id}/{message_id}/{attachment_id}"


def auto_apply_key(user_id: str, auto_apply_id: str, kind: str, filename: str) -> str:
    return f"{user_id}/{auto_apply_id}/{kind}/{filename}"


def cover_letter_key(user_id: str, cover_letter_id: str, ext: str = "md") -> str:
    return f"{user_id}/{cover_letter_id}.{ext}"


def checksum_blob_name(filename: str, checksum_sha256: str) -> str:
    """Stable blob object name: original stem + short checksum + extension."""
    digest = (checksum_sha256 or "0" * 12).replace("/", "")[:12]
    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
        return f"{stem}.{digest}.{ext}"
    return f"{filename}.{digest}"


def config_blob_containers() -> tuple[str, ...]:
    from app.config import get_settings

    settings = get_settings()
    return (
        settings.review_blob_container,
        settings.resume_blob_container,
        settings.job_raw_blob_container,
        settings.mail_blob_container,
    )


def match_explanation_key(user_id: str, match_id: str) -> str:
    return f"{user_id}/{match_id}/explanation.json"


def user_prefix(user_id: str) -> str:
    return f"{user_id}/"


def lifecycle_rules() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for container in BLOB_CONTAINERS:
        actions: dict[str, Any] = {}
        if container.cool_after_days is not None:
            actions["tierToCool"] = {"daysAfterModificationGreaterThan": container.cool_after_days}
        if container.delete_after_days is not None:
            actions["delete"] = {"daysAfterModificationGreaterThan": container.delete_after_days}
        if not actions:
            continue
        rules.append(
            {
                "name": f"{container.name}-lifecycle",
                "container": container.name,
                "enabled": True,
                "filters": {"prefix": ""},
                "actions": actions,
            }
        )
    return rules


def metadata_for(container: str, **tags: str) -> dict[str, str]:
    spec = next((item for item in BLOB_CONTAINERS if item.name == container), None)
    if spec is None:
        return dict(tags)
    allowed = set(spec.metadata_tags)
    return {key: value for key, value in tags.items() if key in allowed}
