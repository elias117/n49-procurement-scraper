"""Query embedding generation using OpenAI API."""
from __future__ import annotations

from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from api import config

# Module-level client (initialized once)
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def embed_query(text: str) -> list[float]:
    """Embed a search query string for pgvector cosine similarity.

    Uses text-embedding-3-small (same model as scraper embeddings).
    Retries up to 3 times with exponential backoff on API errors.

    Args:
        text: The search query string to embed.

    Returns:
        List of 1536 floats (embedding vector).
    """
    client = _get_client()
    response = client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=[text],
    )
    return response.data[0].embedding
