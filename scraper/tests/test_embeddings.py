"""
Tests for embedding generation with batch processing.

All tests mock the OpenAI client to avoid real API calls. Each mock returns
predictable 1536-dimensional embedding vectors.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from scraper.models import ListingRecord
from scraper.pipeline.embeddings import (
    _count_tokens,
    _prepare_embedding_text,
    generate_embeddings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(
    title="Test Procurement",
    description="Test description for embedding.",
    **kwargs,
) -> ListingRecord:
    """Create a ListingRecord with sensible defaults."""
    defaults = {
        "title": title,
        "description": description,
        "source_portal": str(uuid.uuid4()),
        "source_listing_id": f"TEST-{uuid.uuid4().hex[:8]}",
    }
    defaults.update(kwargs)
    return ListingRecord(**defaults)


def _make_mock_response(count: int):
    """
    Create a mock OpenAI embeddings response with `count` embedding objects.
    Each embedding is a 1536-dim vector of 0.01.
    """
    mock_response = MagicMock()
    data = []
    for i in range(count):
        mock_item = MagicMock()
        mock_item.embedding = [0.01] * 1536
        data.append(mock_item)
    mock_response.data = data
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPrepareEmbeddingText:
    """Tests for _prepare_embedding_text()."""

    def test_embedding_text_combines_title_and_description(self):
        """Verify text is 'Title\\n\\nDescription' when both are present."""
        listing = _make_listing(
            title="Network Equipment Supply",
            description="Supply of switches and routers.",
        )
        text = _prepare_embedding_text(listing)
        assert text == "Network Equipment Supply\n\nSupply of switches and routers."

    def test_embedding_text_handles_none_description(self):
        """Verify just the title is returned when description is None."""
        listing = _make_listing(title="Office Supplies", description=None)
        text = _prepare_embedding_text(listing)
        assert text == "Office Supplies"


class TestGenerateEmbeddings:
    """Tests for generate_embeddings()."""

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_generate_embeddings_calls_openai(self, mock_openai_cls):
        """Verify openai.embeddings.create called with correct model."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _make_mock_response(2)

        listings = [_make_listing(), _make_listing()]
        generate_embeddings(listings)

        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args
        assert call_kwargs.kwargs.get("model") or call_kwargs[1].get("model") == "text-embedding-3-small"

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_embeddings_set_on_listings(self, mock_openai_cls):
        """After generate_embeddings, each listing has a 1536-dim vector."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _make_mock_response(3)

        listings = [_make_listing() for _ in range(3)]
        result = generate_embeddings(listings)

        assert len(result) == 3
        for listing in result:
            assert listing.embedding is not None
            assert len(listing.embedding) == 1536
            assert listing.embedding[0] == 0.01

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_batch_splitting_respects_token_limit(self, mock_openai_cls):
        """Listings totalling >250K tokens should require multiple API calls.

        Each text is truncated to 8000 tokens max. We need >250K total tokens
        to trigger splitting: 250K / 8K = ~32 listings minimum.
        Use 35 listings * ~8K tokens each = ~280K tokens > 250K limit.
        """
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Create 35 listings with long descriptions that will each be ~8000
        # tokens after truncation. "procurement " is 1 token + space, so
        # 10000 words will be truncated to 8000 tokens.
        long_text = "procurement " * 10000
        listings = [
            _make_listing(description=long_text) for _ in range(35)
        ]

        # Make create return different sized responses based on input length
        def side_effect(**kwargs):
            input_texts = kwargs.get("input", [])
            return _make_mock_response(len(input_texts))

        mock_client.embeddings.create.side_effect = side_effect

        result = generate_embeddings(listings)

        # Should have been called more than once due to token limit
        call_count = mock_client.embeddings.create.call_count
        assert call_count > 1, (
            f"Expected multiple API calls for ~280K tokens, got {call_count}"
        )
        # All listings should still get embeddings
        for listing in result:
            assert listing.embedding is not None
            assert len(listing.embedding) == 1536

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_long_text_truncated(self, mock_openai_cls):
        """Text exceeding 8000 tokens should be truncated before API call."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _make_mock_response(1)

        # Create listing with very long description (well over 8000 tokens)
        # "procurement " is roughly 1 token per word, so 10000 words
        long_description = "procurement " * 10000
        listing = _make_listing(description=long_description)

        generate_embeddings([listing])

        # Verify the text sent to API was truncated
        call_args = mock_client.embeddings.create.call_args
        input_texts = call_args.kwargs.get("input", call_args[1].get("input", []))
        sent_text = input_texts[0]

        # Count tokens of the sent text -- should be <= 8000
        token_count = _count_tokens(sent_text)
        assert token_count <= 8000, (
            f"Expected truncated text <= 8000 tokens, got {token_count}"
        )

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_empty_list_returns_empty(self, mock_openai_cls):
        """generate_embeddings([]) should return [] without calling API."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        result = generate_embeddings([])

        assert result == []
        mock_client.embeddings.create.assert_not_called()

    @patch("scraper.pipeline.embeddings.OpenAI")
    def test_embedding_model_set_correctly(self, mock_openai_cls):
        """Each listing.embedding_model should be 'text-embedding-3-small'."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _make_mock_response(2)

        listings = [_make_listing(), _make_listing()]
        result = generate_embeddings(listings)

        for listing in result:
            assert listing.embedding_model == "text-embedding-3-small"
