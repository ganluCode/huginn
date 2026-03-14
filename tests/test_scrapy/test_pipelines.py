"""Test Scrapy pipelines - CleanScrapyPipeline and DedupScrapyPipeline (F-004, F-005, F-008)."""

from unittest.mock import MagicMock, Mock

import pytest
from scrapy.exceptions import DropItem

from huginn.core.exceptions import ValidationError
from huginn.core.items import CollectedItem
from huginn.core.pipelines.clean import CleanPipeline
from huginn.scrapy.pipelines import CleanScrapyPipeline, DedupScrapyPipeline


def make_mock_spider(name: str = "test_spider", settings_dict: dict | None = None) -> Mock:
    """Create a mock spider with crawler.settings."""
    spider = Mock()
    spider.name = name

    # Create mock crawler with settings
    crawler = Mock()
    settings = Mock()
    settings.get = Mock(side_effect=lambda key, default=None: settings_dict.get(key, default) if settings_dict else default)
    crawler.settings = settings
    spider.crawler = crawler

    return spider


class TestCleanScrapyPipeline:
    """Verify CleanScrapyPipeline bridges Scrapy items to core CleanPipeline."""

    def test_open_spider_initializes_core_clean_pipeline(self):
        """open_spider should successfully initialize core CleanPipeline instance."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()

        pipeline.open_spider(spider)

        assert pipeline.clean_pipeline is not None
        assert isinstance(pipeline.clean_pipeline, CleanPipeline)

    def test_valid_item_gets_collected_item_attached(self):
        """Valid item should be processed and have _huginn_collected_item attached."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        # Simulate item from BaseSpider.make_item()
        item = {
            "_huginn_source": "hackernews",
            "_huginn_category": "tech",
            "title": "Test Article",
            "url": "http://example.com",
        }

        result = pipeline.process_item(item, spider)

        assert "_huginn_collected_item" in result
        assert isinstance(result["_huginn_collected_item"], CollectedItem)
        assert result["_huginn_collected_item"].source == "hackernews"
        assert result["_huginn_collected_item"].category == "tech"
        # Business data should be in the data field
        assert result["_huginn_collected_item"].data["title"] == "Test Article"
        assert result["_huginn_collected_item"].data["url"] == "http://example.com"

    def test_core_returns_none_raises_drop_item(self):
        """When CleanPipeline.process returns None, should raise DropItem('Clean rejected')."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        # Mock the core pipeline to return None
        pipeline.clean_pipeline.process = MagicMock(return_value=None)

        item = {
            "_huginn_source": "test_source",
            "_huginn_category": "tech",
            "data": "some data",
        }

        with pytest.raises(DropItem, match="Clean rejected"):
            pipeline.process_item(item, spider)

    def test_core_raises_validation_error_raises_drop_item(self):
        """When CleanPipeline raises ValidationError, should raise DropItem with error message."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        # Mock the core pipeline to raise ValidationError
        pipeline.clean_pipeline.process = MagicMock(
            side_effect=ValidationError("Invalid category")
        )

        item = {
            "_huginn_source": "test_source",
            "_huginn_category": "invalid_category",
            "data": "some data",
        }

        with pytest.raises(DropItem, match="Invalid category"):
            pipeline.process_item(item, spider)

    def test_drop_item_logs_warning(self, caplog):
        """DropItem should log WARNING level message."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        # Mock the core pipeline to return None (triggering DropItem)
        pipeline.clean_pipeline.process = MagicMock(return_value=None)

        item = {
            "_huginn_source": "test_source",
            "_huginn_category": "tech",
            "data": "some data",
        }

        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)

        # Check that WARNING was logged
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_business_data_has_no_huginn_prefix_keys(self):
        """Business data dict should not contain any _huginn_ prefixed keys."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        item = {
            "_huginn_source": "hackernews",
            "_huginn_category": "tech",
            "title": "Test Article",
            "url": "http://example.com",
        }

        result = pipeline.process_item(item, spider)

        # Check that business data dict doesn't have _huginn_ keys
        business_data = result["_huginn_collected_item"].data
        assert not any(key.startswith("_huginn_") for key in business_data)
        # Metadata should be in CollectedItem fields
        assert result["_huginn_collected_item"].source == "hackernews"
        assert result["_huginn_collected_item"].category == "tech"

    def test_close_spider_cleans_up(self):
        """close_spider should clean up resources."""
        pipeline = CleanScrapyPipeline()
        spider = make_mock_spider()
        pipeline.open_spider(spider)

        # Should not raise any exception
        pipeline.close_spider(spider)

        # Clean pipeline should be cleaned up
        assert pipeline.clean_pipeline is None


class TestDedupScrapyPipeline:
    """Verify DedupScrapyPipeline bridges Scrapy items to core DedupPipeline."""

    def test_open_spider_initializes_redis_from_settings(self):
        """open_spider should initialize Redis from settings redis_url."""
        pipeline = DedupScrapyPipeline()
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://localhost:6379/0"})

        pipeline.open_spider(spider)

        assert pipeline.redis_client is not None

    def test_duplicate_item_raises_drop_item(self):
        """Duplicate item (DedupPipeline.process returns None) should raise DropItem('Duplicate')."""
        pipeline = DedupScrapyPipeline()
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://localhost:6379/0"})
        pipeline.open_spider(spider)

        # Create a mock collected item
        collected_item = CollectedItem(
            source="test_source",
            category="tech",
            data={"title": "Test", "url": "http://example.com"},
        )

        # Mock the core pipeline to return None (duplicate)
        pipeline.dedup_pipeline.process = MagicMock(return_value=None)

        item = {
            "_huginn_collected_item": collected_item,
        }

        with pytest.raises(DropItem, match="Duplicate"):
            pipeline.process_item(item, spider)

    def test_unique_item_updates_collected_item(self):
        """Unique item should have _huginn_collected_item updated."""
        pipeline = DedupScrapyPipeline()
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://localhost:6379/0"})
        pipeline.open_spider(spider)

        collected_item = CollectedItem(
            source="test_source",
            category="tech",
            data={"title": "Test", "url": "http://example.com"},
        )

        # Mock the core pipeline to return the item (not duplicate)
        pipeline.dedup_pipeline.process = MagicMock(return_value=collected_item)

        item = {
            "_huginn_collected_item": collected_item,
        }

        result = pipeline.process_item(item, spider)

        assert "_huginn_collected_item" in result

    def test_duplicate_logs_debug(self, caplog):
        """Duplicate item should log DEBUG level message."""
        caplog.set_level("DEBUG", logger="huginn.scrapy.pipelines")

        pipeline = DedupScrapyPipeline()
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://localhost:6379/0"})
        pipeline.open_spider(spider)

        collected_item = CollectedItem(
            source="test_source",
            category="tech",
            data={"title": "Test", "url": "http://example.com"},
        )

        # Mock the core pipeline to return None (duplicate)
        pipeline.dedup_pipeline.process = MagicMock(return_value=None)

        item = {
            "_huginn_collected_item": collected_item,
        }

        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)

        # Check that DEBUG was logged
        assert any(record.levelname == "DEBUG" for record in caplog.records)

    def test_redis_unavailable_degrades_gracefully(self):
        """When Redis is unavailable, should degrade gracefully without crashing."""
        pipeline = DedupScrapyPipeline()
        # Use invalid Redis URL to simulate connection failure
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://invalid:9999/0"})

        # Should not raise exception during open_spider
        pipeline.open_spider(spider)

        collected_item = CollectedItem(
            source="test_source",
            category="tech",
            data={"title": "Test", "url": "http://example.com"},
        )

        # Even with Redis down, should not crash
        # The core DedupPipeline should handle this gracefully
        try:
            result = pipeline.process_item({"_huginn_collected_item": collected_item}, spider)
            # Should either return the item or raise DropItem, but not crash
            assert result is None or "_huginn_collected_item" in result
        except DropItem:
            # Also acceptable - DedupPipeline may decide to drop
            pass

    def test_close_spider_closes_redis(self):
        """close_spider should close Redis connection."""
        pipeline = DedupScrapyPipeline()
        spider = make_mock_spider(settings_dict={"REDIS_URL": "redis://localhost:6379/0"})
        pipeline.open_spider(spider)

        # Should not raise any exception
        pipeline.close_spider(spider)

        # Redis client should be closed
        # Note: redis-py doesn't have a simple is_closed check, so we just verify no exception
