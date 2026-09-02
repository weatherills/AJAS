"""Azure OpenAI client factory.

Used by the matching feature for embeddings (semantic similarity) and chat
completions (explanations/summaries). Deployment names are configuration.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from openai import AzureOpenAI


@lru_cache
def get_openai_client() -> "AzureOpenAI":
    """Return a cached Azure OpenAI client built from configuration."""
    from openai import AzureOpenAI

    settings = get_settings()
    if not settings.azure_openai_endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not configured.")
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
