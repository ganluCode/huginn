"""Integration tests for pipeline chain: clean → dedup → storage."""

from unittest.mock import MagicMock

import pytest

from huginn.core.constants import Category
from huginn.core.exceptions import ValidationError
from huginn.core.items import CollectedItem
from huginn.core.pipelines.clean import CleanPipeline
from huginn.core.pipelines.dedup import DedupPipeline
from huginn.core.pipelines.storage import StoragePipeline
from huginn.core.pipelines import run_pipeline_chain


class TestPipelineChain:
    """Integration tests for full pipeline chain."""

    def test_clean_dedup_storage_success(self):
        """Valid item passes through all three pipelines."""
        # Setup mocks
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        mock_backend = MagicMock()
        mock_backend.save_items.return_value = 1

        # Create pipelines
        clean = CleanPipeline()
        dedup = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        storage = StoragePipeline(backend=mock_backend)

        # Create item
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"title": "  hello  world  ", "content": "test content"},
        )

        # Run chain
        result = run_pipeline_chain([clean, dedup, storage], item)

        # Verify result
        assert result == item
        assert result.data["title"] == "hello world"  # Cleaned
        assert result.data["content"] == "test content"

        # Verify dedup and storage were called
        mock_redis.sadd.assert_called_once()
        mock_backend.save_items.assert_called_once()

    def test_clean_validation_stops_chain(self):
        """CleanPipeline validation failure stops chain, propagates ValidationError."""
        # Setup mocks (should not be called)
        mock_redis = MagicMock()
        mock_backend = MagicMock()

        # Create pipelines
        clean = CleanPipeline()
        dedup = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        storage = StoragePipeline(backend=mock_backend)

        # Create invalid item (empty source)
        item = CollectedItem(source="", category=Category.TECH, data={"title": "test"})

        # Run chain - should raise ValidationError
        with pytest.raises(ValidationError, match="source"):
            run_pipeline_chain([clean, dedup, storage], item)

        # Verify dedup and storage were NOT called
        mock_redis.sismember.assert_not_called()
        mock_backend.save_items.assert_not_called()

    def test_dedup_duplicate_stops_chain(self):
        """DedupPipeline detecting duplicate stops chain, returns None."""
        # Setup mocks
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = True  # Duplicate detected
        mock_backend = MagicMock()

        # Create pipelines
        clean = CleanPipeline()
        dedup = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        storage = StoragePipeline(backend=mock_backend)

        # Create item
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        # Run chain - should return None (duplicate)
        result = run_pipeline_chain([clean, dedup, storage], item)

        assert result is None

        # Verify storage was NOT called
        mock_backend.save_items.assert_not_called()

    def test_storage_failure_propagates(self):
        """StoragePipeline failure propagates StorageError."""
        # Setup mocks
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        mock_backend = MagicMock()
        mock_backend.save_items.side_effect = Exception("Database error")

        # Create pipelines
        clean = CleanPipeline()
        dedup = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        storage = StoragePipeline(backend=mock_backend)

        # Create item
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        # Run chain - should raise StorageError
        from huginn.core.exceptions import StorageError

        with pytest.raises(StorageError, match="Failed to save item"):
            run_pipeline_chain([clean, dedup, storage], item)

    def test_full_chain_with_text_cleaning(self):
        """Full chain properly cleans text fields."""
        # Setup mocks
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        mock_backend = MagicMock()
        mock_backend.save_items.return_value = 1

        # Create pipelines
        clean = CleanPipeline()
        dedup = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        storage = StoragePipeline(backend=mock_backend)

        # Create item with messy text
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"title": "\t\n  Hello\t\tWorld\n\n  ", "count": 123},
        )

        # Run chain
        result = run_pipeline_chain([clean, dedup, storage], item)

        # Verify text was cleaned
        assert result.data["title"] == "Hello World"
        assert result.data["count"] == 123  # Non-string unchanged

        # Verify storage got cleaned data
        mock_backend.save_items.assert_called_once()
        call_args = mock_backend.save_items.call_args
        assert call_args[0][2][0]["title"] == "Hello World"
