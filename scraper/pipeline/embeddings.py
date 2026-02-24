"""
Embedding generation with batch processing.

Generates text-embedding-3-small embeddings for procurement listings using the
OpenAI API. Batches requests to stay under the 250K token limit and 2048 items
per request. Retries on rate limits and connection errors.

IMPORTANT: Embeddings should be generated AFTER validation. Do not waste
embedding tokens on invalid listings.
"""

import logging
from typing import List

import tiktoken
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper import config
from scraper.models import ListingRecord

logger = logging.getLogger("scraper.embeddings")

# Lazily initialized tiktoken encoder
_encoder = None


def _get_encoder():
    """Get the cl100k_base tiktoken encoder (lazy singleton)."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def _prepare_embedding_text(listing: ListingRecord) -> str:
    """
    Combine title and description into embedding text.

    Format: "Title\\n\\nDescription" (or just "Title" if no description).

    Args:
        listing: A ListingRecord to prepare text for.

    Returns:
        The prepared embedding text string.
    """
    if listing.description:
        return f"{listing.title}\n\n{listing.description}".strip()
    return listing.title.strip()


def _count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using cl100k_base encoding.

    Args:
        text: The text to count tokens for.

    Returns:
        The token count.
    """
    encoder = _get_encoder()
    return len(encoder.encode(text))


def _truncate_text(text: str, max_tokens: int) -> str:
    """
    Truncate text to a maximum number of tokens.

    Args:
        text: The text to truncate.
        max_tokens: Maximum number of tokens allowed.

    Returns:
        The truncated text.
    """
    encoder = _get_encoder()
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoder.decode(tokens[:max_tokens])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_embeddings_api(client: OpenAI, texts: List[str], model: str):
    """
    Call the OpenAI embeddings API with retry logic.

    Retries up to 3 times with exponential backoff on RateLimitError
    and APIConnectionError.

    Args:
        client: The OpenAI client instance.
        texts: List of text strings to embed.
        model: The embedding model name.

    Returns:
        The API response object.
    """
    return client.embeddings.create(model=model, input=texts)


def generate_embeddings(listings: List[ListingRecord]) -> List[ListingRecord]:
    """
    Generate embeddings for a list of ListingRecord objects.

    Processes listings in batches respecting:
    - Max 250,000 tokens per API request (EMBEDDING_BATCH_TOKEN_LIMIT)
    - Max 2048 items per API request (EMBEDDING_BATCH_SIZE_LIMIT)

    Each listing's embedding text is truncated to 8000 tokens
    (MAX_EMBEDDING_TOKENS) before being sent to the API.

    Args:
        listings: List of ListingRecord objects to generate embeddings for.

    Returns:
        The same list of ListingRecord objects with embedding and
        embedding_model fields populated.
    """
    if not listings:
        return listings

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    model = config.OPENAI_EMBEDDING_MODEL
    max_tokens_per_text = config.MAX_EMBEDDING_TOKENS
    batch_token_limit = config.EMBEDDING_BATCH_TOKEN_LIMIT
    batch_size_limit = config.EMBEDDING_BATCH_SIZE_LIMIT

    # Prepare and truncate all texts, count tokens
    prepared = []
    for listing in listings:
        text = _prepare_embedding_text(listing)
        text = _truncate_text(text, max_tokens_per_text)
        token_count = _count_tokens(text)
        prepared.append((text, token_count))

    # Build batches respecting both limits
    batches = []
    current_batch_texts = []
    current_batch_indices = []
    current_batch_tokens = 0

    for i, (text, token_count) in enumerate(prepared):
        # Check if adding this item would exceed either limit
        would_exceed_tokens = (current_batch_tokens + token_count) > batch_token_limit
        would_exceed_size = len(current_batch_texts) >= batch_size_limit

        if current_batch_texts and (would_exceed_tokens or would_exceed_size):
            batches.append((current_batch_texts, current_batch_indices))
            current_batch_texts = []
            current_batch_indices = []
            current_batch_tokens = 0

        current_batch_texts.append(text)
        current_batch_indices.append(i)
        current_batch_tokens += token_count

    # Don't forget the last batch
    if current_batch_texts:
        batches.append((current_batch_texts, current_batch_indices))

    # Process batches
    total_tokens = sum(tc for _, tc in prepared)
    api_calls = 0

    for batch_texts, batch_indices in batches:
        response = _call_embeddings_api(client, batch_texts, model)
        api_calls += 1

        for j, embedding_data in enumerate(response.data):
            listing_idx = batch_indices[j]
            listings[listing_idx].embedding = embedding_data.embedding
            listings[listing_idx].embedding_model = model

    logger.info(
        "Embedding generation complete: %d listings, %d API calls, %d total tokens.",
        len(listings),
        api_calls,
        total_tokens,
    )

    return listings
