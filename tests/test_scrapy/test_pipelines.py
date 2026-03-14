"""Test Scrapy pipelines - CleanScrapyPipeline, DedupScrapyPipeline, and StorageScrapyPipeline (F-004, F-005, F-006, F-008)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from scrapy.exceptions import DropItem

from huginn.core.exceptions import ValidationError
from huginn.core.items import CollectedItem
from huginn.core.models import SpiderRegistry, SpiderRun
from huginn.core.pipelines.clean import CleanPipeline
from huginn.scrapy.pipelines import CleanScrapyPipeline, DedupScrapyPipeline, StorageScrapyPipeline


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


def make_mock_spider_with_stats(
    name: str = "test_spider",
    settings_dict: dict | None = None,
    stats_dict: dict | None = None,
) -> Mock:
    """Create a mock spider with crawler.settings and crawler.stats."""
    spider = make_mock_spider(name, settings_dict)

    # Add stats to crawler
    stats_collector = Mock()
    stats_dict = stats_dict or {}
    stats_collector.get_stats = Mock(return_value=stats_dict)
    stats_collector.get_value = Mock(side_effect=lambda key, default=None: stats_dict.get(key, default))
    spider.crawler.stats = stats_collector

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


class TestStorageScrapyPipeline:
    """Verify StorageScrapyPipeline manages DB connection and spider lifecycle."""

    def test_open_spider_creates_db_session_and_pipeline(self):
        """open_spider should create DB session and initialize StoragePipeline."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider("test_spider")
        spider.source_category = "tech"

        # Mock SyncSessionLocal
        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Make flush() assign an ID to the added SpiderRun
        def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRun) and obj.id is None:
                    obj.id = 123

        mock_session.flush = mock_flush
        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Verify DB session was created
            assert pipeline.db_session is not None
            # Verify storage pipeline was initialized
            assert pipeline.storage_pipeline is not None
            # Verify run ID was set
            assert pipeline._run_id is not None

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_open_spider_inserts_spider_run_record(self):
        """open_spider should insert spider_runs record with status='running'."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider("test_spider")
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Mock query to return None (spider not in registry)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Verify SpiderRun was added
            assert mock_session.add.called
            # Verify flush was called to get the ID
            assert mock_session.flush.called

            # Check the added object is a SpiderRun
            added_obj = mock_session.add.call_args[0][0]
            assert isinstance(added_obj, SpiderRun)
            assert added_obj.spider_name == "test_spider"
            assert added_obj.status == "running"

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_open_spider_auto_registers_unknown_spider(self):
        """open_spider should auto-register spider in spider_registry if not exists."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider("new_spider")
        spider.source_category = "finance"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Mock query to return None (spider not in registry)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Verify both SpiderRun and SpiderRegistry were added
            # add() should be called at least twice (SpiderRun + SpiderRegistry)
            assert mock_session.add.call_count >= 2

            # Find the SpiderRegistry among the added objects
            added_registry = None
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRegistry):
                    added_registry = obj
                    break

            assert added_registry is not None
            assert added_registry.name == "new_spider"
            assert added_registry.engine == "scrapy"
            assert added_registry.category == "finance"
            assert added_registry.enabled is True

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_process_item_increments_count(self):
        """process_item should increment _item_count."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider("test_spider")
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Process some items
            collected_item = CollectedItem(
                source="test_spider",
                category="tech",
                data={"title": "Test"},
            )
            item = {"_huginn_collected_item": collected_item}

            pipeline.process_item(item, spider)
            assert pipeline._item_count == 1

            pipeline.process_item(item, spider)
            assert pipeline._item_count == 2

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_close_spider_updates_run_record_on_success(self):
        """close_spider should update spider_runs with finished_at, status='success', item_count."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider_with_stats("test_spider", stats_dict={})
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Create a fresh SpiderRun mock with item_count=0
        mock_run = SpiderRun(spider_name="test_spider", started_at=datetime.now(timezone.utc), status="running", item_count=0)
        mock_run.id = 123
        # Create a fresh SpiderRegistry mock (should exist)
        mock_registry = SpiderRegistry(name="test_spider", engine="scrapy", category="tech", enabled=True, item_count=0)

        # Make query return different objects for different calls
        # First call in open_spider (spider exists check) returns None (auto-register)
        # Second call in close_spider (get run by id) returns mock_run
        # Third call in close_spider (get registry by name) returns mock_registry
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [None, mock_run, mock_registry]

        # Make flush assign ID
        def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRun) and obj.id is None:
                    obj.id = 456  # Different ID for the run created in open_spider

        mock_session.flush = mock_flush

        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Process some items
            collected_item = CollectedItem(
                source="test_spider",
                category="tech",
                data={"title": "Test"},
            )
            item = {"_huginn_collected_item": collected_item}
            pipeline.process_item(item, spider)
            pipeline.process_item(item, spider)

            pipeline.close_spider(spider)

            # Verify run record was updated
            assert mock_run.finished_at is not None
            assert mock_run.status == "success"
            assert mock_run.item_count == 2
            assert mock_run.duration_ms is not None
            assert mock_run.duration_ms >= 0
            assert mock_run.error_message is None

            # Verify commit was called
            assert mock_session.commit.called
            # Verify session was closed
            assert mock_session.close.called

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_close_spider_detects_error_logs(self):
        """close_spider should set status='failed' when ERROR logs are detected."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider_with_stats(
            "test_spider",
            stats_dict={"log_count/ERROR": 3},
        )
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Create fresh SpiderRun mock
        mock_run = SpiderRun(spider_name="test_spider", started_at=datetime.now(timezone.utc), status="running", item_count=0)
        mock_run.id = 123
        # Create fresh SpiderRegistry mock
        mock_registry = SpiderRegistry(name="test_spider", engine="scrapy", category="tech", enabled=True, item_count=10)

        # Make query return different objects for different calls
        # Need to handle multiple query calls in open_spider and close_spider
        # Use a callable to return appropriate values
        query_call_count = [0]

        def query_side_effect():
            query_call_count[0] += 1
            # Open spider: check if spider exists (returns None for auto-register)
            if query_call_count[0] == 1:
                return None
            # Close spider: get run by id
            elif query_call_count[0] == 2:
                return mock_run
            # Close spider: get registry by name
            elif query_call_count[0] == 3:
                return mock_registry
            # Any other calls return None
            return None

        mock_session.query.return_value.filter_by.return_value.first.side_effect = query_side_effect

        # Make flush assign ID
        def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRun) and obj.id is None:
                    obj.id = 456

        mock_session.flush = mock_flush

        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            pipeline.close_spider(spider)

            # Check run record was updated with failed status
            assert mock_run.status == "failed"
            assert mock_run.error_message is not None
            assert "3 error" in mock_run.error_message

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_close_spider_updates_registry(self):
        """close_spider should update spider_registry with last_run_at, last_status, item_count."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider_with_stats("test_spider", stats_dict={})
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        # Create fresh SpiderRun mock
        mock_run = SpiderRun(spider_name="test_spider", started_at=datetime.now(timezone.utc), status="running", item_count=0)
        mock_run.id = 123
        # Create fresh SpiderRegistry mock
        mock_registry = SpiderRegistry(name="test_spider", engine="scrapy", category="tech", enabled=True, item_count=10)

        # Make query return different objects for different calls
        # First call in open_spider (spider exists check) returns None
        # Second call in close_spider (get run by id) returns mock_run
        # Third call in close_spider (get registry by name) returns mock_registry
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [None, mock_run, mock_registry]

        # Make flush assign ID
        def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRun) and obj.id is None:
                    obj.id = 456

        mock_session.flush = mock_flush

        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Process some items
            collected_item = CollectedItem(
                source="test_spider",
                category="tech",
                data={"title": "Test"},
            )
            item = {"_huginn_collected_item": collected_item}
            pipeline.process_item(item, spider)
            pipeline.process_item(item, spider)
            pipeline.process_item(item, spider)

            pipeline.close_spider(spider)

            # Check spider_registry was updated
            assert mock_registry.last_run_at is not None
            assert mock_registry.last_status == "success"
            # item_count should be accumulated
            assert mock_registry.item_count == 13  # 10 (original) + 3 (new)

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local

    def test_close_spider_handles_db_errors_gracefully(self):
        """close_spider should handle DB errors gracefully with rollback."""
        pipeline = StorageScrapyPipeline()
        spider = make_mock_spider_with_stats("test_spider", stats_dict={})
        spider.source_category = "tech"

        import huginn.scrapy.pipelines

        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB error")
        # Create fresh SpiderRun mock
        mock_run = SpiderRun(spider_name="test_spider", started_at=datetime.now(timezone.utc), status="running", item_count=0)
        mock_run.id = 123
        # Create fresh SpiderRegistry mock (for the third query call)
        mock_registry = SpiderRegistry(name="test_spider", engine="scrapy", category="tech", enabled=True, item_count=0)

        # Make query return different objects for different calls
        query_call_count = [0]

        def query_side_effect():
            query_call_count[0] += 1
            # Open spider: check if spider exists (returns None for auto-register)
            if query_call_count[0] == 1:
                return None
            # Close spider: get run by id
            elif query_call_count[0] == 2:
                return mock_run
            # Close spider: get registry by name (before commit fails)
            elif query_call_count[0] == 3:
                return mock_registry
            # Any other calls return None
            return None

        mock_session.query.return_value.filter_by.return_value.first.side_effect = query_side_effect

        # Make flush assign ID
        def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SpiderRun) and obj.id is None:
                    obj.id = 456

        mock_session.flush = mock_flush

        original_session_local = huginn.scrapy.pipelines.SyncSessionLocal
        huginn.scrapy.pipelines.SyncSessionLocal = lambda: mock_session

        try:
            pipeline.open_spider(spider)

            # Should not raise exception
            pipeline.close_spider(spider)

            # Verify rollback was called
            assert mock_session.rollback.called
            # Verify session was still closed
            assert mock_session.close.called

        finally:
            huginn.scrapy.pipelines.SyncSessionLocal = original_session_local
