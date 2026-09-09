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

    match_compute_queue: str = "match-compute"
    match_poison_dequeue: int = 5
    match_sync_rate_per_minute: int = 60
    match_max_text_chars: int = 100_000
    match_max_rank_pairs: int = 1000
    match_rank_async_after: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from the environment."""
    return Settings()
