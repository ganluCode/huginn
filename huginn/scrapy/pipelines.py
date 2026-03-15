"""Scrapy pipelines for Huginn.

This module provides Scrapy pipeline implementations that bridge Scrapy items
to the core Huginn pipelines (clean, dedup, storage).

Pipelines:
- CleanScrapyPipeline (priority 100): Validates and cleans items
- DedupScrapyPipeline (priority 200): Deduplicates items using Redis
- StorageScrapyPipeline (priority 300): Persists items to database
"""

import logging
from datetime import UTC, datetime

from scrapy.exceptions import DropItem
from scrapy.spiders import Spider
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from huginn.core.db import SyncSessionLocal
from huginn.core.items import CollectedItem
from huginn.core.models import SpiderRegistry, SpiderRun
from huginn.core.pipelines.clean import CleanPipeline
from huginn.core.pipelines.dedup import DedupPipeline
from huginn.core.pipelines.storage import StoragePipeline

logger = logging.getLogger(__name__)


class CleanScrapyPipeline:
    """Scrapy pipeline for validating and cleaning items.

    Bridges Scrapy items to the core CleanPipeline. Extracts metadata
    (_huginn_source, _huginn_category) from the item and creates a CollectedItem
    with business data (fields without _huginn_ prefix).

    The cleaned CollectedItem is attached to the item as _huginn_collected_item
    for subsequent pipelines to use.
    """

    def __init__(self):
        """Initialize the pipeline."""
        self.clean_pipeline: CleanPipeline | None = None

    def open_spider(self, spider: Spider) -> None:
        """Initialize the core CleanPipeline when spider opens.

        Args:
            spider: The Scrapy spider instance.
        """
        self.clean_pipeline = CleanPipeline()
        logger.debug("CleanScrapyPipeline initialized for spider: %s", spider.name)

    def process_item(self, item: dict, spider: Spider) -> dict:
        """Process and validate an item.

        Extracts metadata and business data from the item, validates it using
        the core CleanPipeline, and attaches the cleaned CollectedItem.

        Args:
            item: The Scrapy item (dict) from BaseSpider.make_item().
            spider: The Scrapy spider instance.

        Returns:
            The item with _huginn_collected_item attached.

        Raises:
            DropItem: If validation fails (CleanPipeline returns None or raises ValidationError).
        """
        if self.clean_pipeline is None:
            logger.error("CleanPipeline not initialized")
            raise DropItem("CleanPipeline not initialized")

        # Extract metadata
        source = item.get("_huginn_source", spider.name)
        category = item.get("_huginn_category", getattr(spider, "source_category", "unknown"))

        # Extract business data (all fields except _huginn_ prefixed ones)
        business_data = {k: v for k, v in item.items() if not k.startswith("_huginn_")}

        # Build CollectedItem
        collected_item = CollectedItem(
            source=source,
            category=category,
            data=business_data,
        )

        # Process through core CleanPipeline
        try:
            result = self.clean_pipeline.process(collected_item)
            if result is None:
                logger.warning("Item rejected by CleanPipeline: source=%s", source)
                raise DropItem("Clean rejected")
        except DropItem:
            # Re-raise DropItem as-is
            raise
        except Exception as e:
            # Convert other exceptions to DropItem
            error_msg = str(e)
            logger.warning("Item validation failed: %s", error_msg)
            raise DropItem(error_msg) from None

        # Attach the cleaned CollectedItem to the item
        item["_huginn_collected_item"] = result
        return item

    def close_spider(self, spider: Spider) -> None:
        """Clean up when spider closes.

        Args:
            spider: The Scrapy spider instance.
        """
        self.clean_pipeline = None
        logger.debug("CleanScrapyPipeline closed for spider: %s", spider.name)


class DedupScrapyPipeline:
    """Scrapy pipeline for deduplicating items.

    Bridges Scrapy items to the core DedupPipeline. Uses Redis to track
    seen items by content hash. Items already seen are dropped.

    The pipeline is resilient to Redis unavailability - if Redis is down,
    items will pass through (degraded mode) rather than blocking the crawl.
    """

    def __init__(self):
        """Initialize the pipeline."""
        self.redis_url: str | None = None
        self.redis_client = None
        self.dedup_pipeline: DedupPipeline | None = None

    def open_spider(self, spider: Spider) -> None:
        """Initialize Redis connection and core DedupPipeline when spider opens.

        Gets redis_url from Scrapy settings.

        Args:
            spider: The Scrapy spider instance.
        """
        # Get redis_url from settings
        settings = spider.crawler.settings
        self.redis_url = settings.get("REDIS_URL", "redis://localhost:6379/0")

        try:
            # Initialize synchronous Redis client
            from redis import Redis

            self.redis_client = Redis.from_url(self.redis_url, decode_responses=True)

            # Initialize core DedupPipeline
            self.dedup_pipeline = DedupPipeline(
                redis_url=self.redis_url,
                _redis_client=self.redis_client,
            )

            logger.debug("DedupScrapyPipeline initialized for spider: %s", spider.name)
        except Exception as e:
            logger.warning(
                "Failed to initialize DedupScrapyPipeline (Redis unavailable): %s. "
                "Deduplication will be disabled.",
                e,
            )
            self.redis_client = None
            self.dedup_pipeline = None

    def process_item(self, item: dict, spider: Spider) -> dict:  # noqa: ARG002
        """Check if item is duplicate and filter if so.

        Expects _huginn_collected_item to be attached by CleanScrapyPipeline.

        Args:
            item: The Scrapy item with _huginn_collected_item.
            spider: The Scrapy spider instance (unused but required by Scrapy API).

        Returns:
            The item with updated _huginn_collected_item.

        Raises:
            DropItem: If item is a duplicate.
        """
        # Get CollectedItem from previous pipeline
        collected_item = item.get("_huginn_collected_item")
        if collected_item is None:
            logger.warning("No _huginn_collected_item found, skipping deduplication")
            return item

        # If DedupPipeline failed to initialize, skip deduplication (degraded mode)
        if self.dedup_pipeline is None:
            logger.debug("DedupPipeline not initialized, skipping deduplication")
            return item

        # Process through core DedupPipeline
        result = self.dedup_pipeline.process(collected_item)

        if result is None:
            # Item is a duplicate
            logger.debug(
                "Duplicate item dropped: source=%s",
                collected_item.source,
            )
            raise DropItem("Duplicate")

        # Update the collected item in case it was modified
        item["_huginn_collected_item"] = result
        return item

    def close_spider(self, spider: Spider) -> None:
        """Close Redis connection when spider closes.

        Args:
            spider: The Scrapy spider instance.
        """
        if self.redis_client is not None:
            try:
                self.redis_client.close()
            except Exception as e:
                logger.warning("Error closing Redis connection: %s", e)

        self.redis_client = None
        self.dedup_pipeline = None
        logger.debug("DedupScrapyPipeline closed for spider: %s", spider.name)


class StorageScrapyPipeline:
    """Scrapy pipeline for storing items.

    Bridges Scrapy items to the core StoragePipeline. Persists items
    to the database and tracks spider runs.

    Manages the spider lifecycle:
    - open_spider: Creates DB session, inserts spider_runs record, registers spider
    - process_item: Counts items for tracking
    - close_spider: Updates spider_runs and spider_registry, detects errors
    """

    def __init__(self):
        """Initialize the pipeline."""
        self.db_session: Session | None = None
        self.storage_pipeline: StoragePipeline | None = None
        self._run_id: int | None = None
        self._item_count: int = 0
        self._started_at: datetime | None = None

    def open_spider(self, spider: Spider) -> None:
        """Initialize database connection and tracking when spider opens.

        Creates a synchronous DB session, initializes the core StoragePipeline,
        inserts a spider_runs record with status='running', and auto-registers
        the spider in spider_registry if it doesn't exist.

        Args:
            spider: The Scrapy spider instance.
        """
        # Create synchronous DB session
        self.db_session = SyncSessionLocal()
        logger.info("StorageScrapyPipeline opened DB session for spider: %s", spider.name)

        # Initialize core StoragePipeline with PostgresBackend
        # Note: We create a backend that uses sync session internally
        backend = _SyncPostgresBackend(self.db_session)
        self.storage_pipeline = StoragePipeline(backend)

        # Record start time
        self._started_at = datetime.now(UTC)
        self._item_count = 0

        # Auto-register spider in spider_registry if not exists
        self._ensure_spider_registered(spider)

        # Insert spider_runs record with status='running'
        run = SpiderRun(
            spider_name=spider.name,
            started_at=self._started_at,
            status="running",
            item_count=0,
        )
        self.db_session.add(run)
        self.db_session.flush()  # Get the ID without committing
        self._run_id = run.id

        logger.info("Started spider run: spider=%s, run_id=%s", spider.name, self._run_id)

    def _ensure_spider_registered(self, spider: Spider) -> None:
        """Ensure spider is registered in spider_registry.

        If the spider doesn't exist in spider_registry, insert a new record
        with engine='scrapy', category=spider.source_category, enabled=True.

        Args:
            spider: The Scrapy spider instance.
        """
        if self.db_session is None:
            logger.warning("DB session not available, skipping spider registration")
            return

        # Check if spider exists
        existing = self.db_session.query(SpiderRegistry).filter_by(name=spider.name).first()

        if existing is None:
            # Auto-register the spider
            category = getattr(spider, "source_category", "unknown")
            registry = SpiderRegistry(
                name=spider.name,
                engine="scrapy",
                category=category,
                enabled=True,
                item_count=0,
            )
            self.db_session.add(registry)
            self.db_session.flush()
            logger.info(
                "Auto-registered spider: name=%s, category=%s, engine=scrapy",
                spider.name,
                category,
            )
        else:
            logger.debug("Spider already registered: %s", spider.name)

    def process_item(self, item: dict, spider: Spider) -> dict:  # noqa: ARG002
        """Store item to database and count items.

        Delegates the actual storage to the core StoragePipeline (which saves
        items in batches). This method mainly counts items for tracking.

        Args:
            item: The Scrapy item with _huginn_collected_item.
            spider: The Scrapy spider instance (unused but required by Scrapy API).

        Returns:
            The item.
        """
        # Increment item count for tracking
        self._item_count += 1

        # Get the CollectedItem from previous pipeline
        collected_item = item.get("_huginn_collected_item")
        if collected_item is None:
            logger.warning("No _huginn_collected_item found, skipping storage")
            return item

        # Store using core StoragePipeline
        if self.storage_pipeline is not None:
            try:
                self.storage_pipeline.process(collected_item)
            except Exception as e:
                logger.error("Failed to store item: %s", e)
                # Re-raise to let Scrapy handle the error
                raise

        return item

    def close_spider(self, spider: Spider) -> None:
        """Update run status and close database connection.

        Updates the spider_runs record with finished_at, status, item_count,
        and duration_ms. Also updates spider_registry with last_run_at,
        last_status, and accumulates item_count.

        If there were ERROR logs during the run (detected via stats),
        sets status to 'failed' and records error_message.

        Args:
            spider: The Scrapy spider instance.
        """
        if self.db_session is None:
            logger.warning("DB session not available, skipping cleanup")
            return

        # Calculate duration
        finished_at = datetime.now(UTC)
        duration_ms = 0
        if self._started_at is not None:
            duration_ms = int((finished_at - self._started_at).total_seconds() * 1000)

        # Check for ERROR logs in stats
        stats = spider.crawler.stats.get_stats()
        error_count = stats.get("log_count/ERROR", 0)

        # Determine status and error message
        status = "success"
        error_message = None

        if error_count > 0:
            status = "failed"
            error_message = f"Spider encountered {error_count} error(s) during execution"
            logger.warning("Spider run had errors: %s", error_message)

        # Update spider_runs record
        if self._run_id is not None:
            run = self.db_session.query(SpiderRun).filter_by(id=self._run_id).first()
            if run is not None:
                run.finished_at = finished_at
                run.status = status
                run.item_count = self._item_count
                run.duration_ms = duration_ms
                run.error_message = error_message

        # Update spider_registry
        registry = self.db_session.query(SpiderRegistry).filter_by(name=spider.name).first()
        if registry is not None:
            registry.last_run_at = finished_at
            registry.last_status = status
            # Accumulate item count (not replace)
            registry.item_count = (registry.item_count or 0) + self._item_count

        # Commit all changes
        try:
            self.db_session.commit()
            logger.info(
                "Finished spider run: spider=%s, run_id=%s, status=%s, items=%d, duration_ms=%d",
                spider.name,
                self._run_id,
                status,
                self._item_count,
                duration_ms,
            )
        except Exception as e:
            self.db_session.rollback()
            logger.error("Failed to commit spider run updates: %s", e)
        finally:
            # Close DB session
            self.db_session.close()
            self.db_session = None
            self.storage_pipeline = None


class _SyncPostgresBackend:
    """Synchronous PostgresBackend wrapper for StoragePipeline.

    The core StoragePipeline expects an async backend, but in Scrapy pipelines
    we need to work with synchronous sessions. This adapter wraps the sync session
    and provides a synchronous save_items method.

    This is an internal adapter class used only by StorageScrapyPipeline.
    """

    def __init__(self, session: Session):
        """Initialize the sync backend.

        Args:
            session: SQLAlchemy synchronous session.
        """
        self._session = session

    def save_items(self, source: str, category: str, items: list[dict]) -> int:
        """Synchronously save items to the database.

        Args:
            source: Data source identifier.
            category: Data category.
            items: List of item data dictionaries.

        Returns:
            Number of items saved.
        """
        from huginn.core.models import CollectedData

        if not items:
            return 0

        try:
            # Build records for batch insert
            records = [
                {
                    "source": source,
                    "category": category,
                    "data": item,
                    "collected_at": datetime.now(UTC),
                }
                for item in items
            ]

            # Execute bulk insert
            self._session.execute(pg_insert(CollectedData).returning(CollectedData.id), records)
            self._session.commit()

            logger.debug("Saved %d items for source=%s", len(items), source)
            return len(items)

        except Exception as e:
            self._session.rollback()
            logger.error("Failed to save items for source=%s: %s", source, e)
            raise
