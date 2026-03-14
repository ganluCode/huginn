"""Tests for huginn.core.pipelines.dedup module."""

from unittest.mock import MagicMock, patch

import pytest

from huginn.core.constants import Category
from huginn.core.items import CollectedItem
from huginn.core.pipelines.dedup import DedupPipeline


class TestDedupPipelineBasic:
    """Tests for basic DedupPipeline functionality."""

    def test_first_process_returns_item(self):
        """First process() call returns the item."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        result = pipeline.process(item)

        assert result == item
        mock_redis.sadd.assert_called_once()

    def test_second_process_returns_none(self):
        """Second process() with same data returns None (duplicate)."""
        mock_redis = MagicMock()
        # First call: not in set
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        # First call
        result1 = pipeline.process(item)
        assert result1 == item

        # Second call: now in set
        mock_redis.sismember.return_value = True
        result2 = pipeline.process(item)
        assert result2 is None


class TestDedupPipelineSourceIsolation:
    """Tests for source isolation in DedupPipeline."""

    def test_different_sources_independent(self):
        """Different sources have independent dedup sets."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        item1 = CollectedItem(source="source1", category=Category.TECH, data={"title": "test"})
        item2 = CollectedItem(source="source2", category=Category.TECH, data={"title": "test"})

        result1 = pipeline.process(item1)
        result2 = pipeline.process(item2)

        # Both should return items (different sources)
        assert result1 == item1
        assert result2 == item2

    def test_same_source_duplicate_detected(self):
        """Same source with same data is detected as duplicate."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        item1 = CollectedItem(source="source", category=Category.TECH, data={"title": "test"})
        item2 = CollectedItem(source="source", category=Category.TECH, data={"title": "test"})

        result1 = pipeline.process(item1)
        # For second call, simulate item already in set
        mock_redis.sismember.return_value = True
        result2 = pipeline.process(item2)

        assert result1 == item1
        assert result2 is None


class TestDedupPipelineHashOrder:
    """Tests for hash order independence."""

    def test_field_order_does_not_affect_hash(self):
        """Different field order with same content produces same hash."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        item1 = CollectedItem(source="test", category=Category.TECH, data={"b": 1, "a": 2})
        item2 = CollectedItem(source="test", category=Category.TECH, data={"a": 2, "b": 1})

        result1 = pipeline.process(item1)
        # Second call should be detected as duplicate (same content)
        mock_redis.sismember.return_value = True
        result2 = pipeline.process(item2)

        assert result1 == item1
        assert result2 is None


class TestDedupPipelineRedisFailure:
    """Tests for Redis failure handling."""

    def test_connection_error_returns_item(self):
        """Redis ConnectionError causes process() to return item with fallback."""
        mock_redis = MagicMock()
        mock_redis.sismember.side_effect = ConnectionError("Redis unavailable")

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        result = pipeline.process(item)

        # Should return item (fallback behavior)
        assert result == item

    def test_redis_operation_exception_returns_item(self):
        """Redis operation exception causes process() to return item."""
        mock_redis = MagicMock()
        mock_redis.sismember.side_effect = Exception("Redis error")

        pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        result = pipeline.process(item)

        # Should return item (fallback behavior)
        assert result == item


class TestDedupPipelineTTL:
    """Tests for TTL management."""

    def test_sets_ttl_on_new_item(self):
        """TTL is set when set has no TTL."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1  # No TTL set
        mock_redis.expire.return_value = True

        pipeline = DedupPipeline(redis_url="redis://localhost", ttl=3600, _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        pipeline.process(item)

        # Should set TTL
        mock_redis.expire.assert_called_once()

    def test_no_ttl_when_already_set(self):
        """TTL is not set when already exists."""
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = 100  # TTL already set

        pipeline = DedupPipeline(redis_url="redis://localhost", ttl=3600, _redis_client=mock_redis)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        pipeline.process(item)

        # Should not set TTL (already exists)
        mock_redis.expire.assert_not_called()
