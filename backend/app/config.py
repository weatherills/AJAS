"""Application configuration.

Settings are read from environment variables (Azure Functions app settings /
`local.settings.json` locally). Values are intentionally optional with safe
defaults so the app imports and starts before every backing service is wired
up; feature code should validate that the settings it needs are present.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Cosmos DB (JobPosting / Match / Application / resume metadata, etc.)
    cosmos_connection_string: str = ""
    cosmos_database: str = "ajas"

    # Azure Storage (Blob for resumes/raw payloads, Queues for async pipelines).
    # Defaults target the local Azurite emulator.
    blob_connection_string: str = "UseDevelopmentStorage=true"
    queue_connection_string: str = "UseDevelopmentStorage=true"

    # Azure OpenAI (embeddings + summaries for matching).
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_embeddings_deployment: str = "text-embedding-3-small"
    azure_openai_chat_deployment: str = "gpt-4o-mini"

    # Auth: "dev" accepts Bearer <user_id>; "aad" validates a JWT.
    auth_mode: str = "dev"
    auth_jwt_secret: str = ""
    auth_jwt_audience: str = ""
    auth_jwt_jwks_url: str = ""

    review_decision_queue: str = "decision-events"
    review_enrich_queue: str = "review-enrich"
    review_poison_dequeue: int = 5
    review_overwrite_hours: int = 24
    review_sas_minutes: int = 10
    review_blob_container: str = "review-artifacts"

    auto_apply_request_queue: str = "auto-apply-requests"
    auto_apply_submit_queue: str = "auto-apply-submits"
    auto_apply_webhook_queue: str = "auto-apply-webhooks"
    auto_apply_poison_dequeue: int = 5
    auto_apply_sas_minutes: int = 10
    auto_apply_webhook_secret: str = "dev-webhook-secret"

    microsoft_tenant: str = "common"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    settings_token_key: str = "dev-settings-token-key"
    settings_write_rate_per_minute: int = 10
    settings_connect_rate_per_minute: int = 3
    match_recalc_queue: str = "match-recalc"
    source_discovery_queue: str = "source-discovery"
    learning_decisions_queue: str = "learning-decisions"

    resume_blob_container: str = "resumes"
    resume_parse_queue: str = "resume-parse"
    resume_max_upload_bytes: int = 10 * 1024 * 1024
    resume_max_pdf_pages: int = 20
    resume_upload_rate_per_hour: int = 30
    resume_max_concurrent_parses: int = 5

    crawl_runs_queue: str = "crawl-runs"
    job_fetch_queue: str = "job-fetch"
    job_raw_blob_container: str = "job-raw"
    crawl_poison_dequeue: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from the environment."""
    return Settings()
