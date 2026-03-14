"""Scrapy pipelines for Huginn.

This module provides Scrapy pipeline implementations that bridge Scrapy items
to the core Huginn pipelines (clean, dedup, storage).

Pipelines:
- CleanScrapyPipeline (priority 100): Validates and cleans items
- DedupScrapyPipeline (priority 200): Deduplicates items using Redis
- StorageScrapyPipeline (priority 300): Persists items to database
"""

import logging

from scrapy.exceptions import DropItem
from scrapy.spiders import Spider

from huginn.core.items import CollectedItem
from huginn.core.pipelines.clean import CleanPipeline
from huginn.core.pipelines.dedup import DedupPipeline

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

    This is a placeholder for F-006 implementation.
    """

    def open_spider(self, spider: Spider) -> None:
        """Initialize database connection and tracking when spider opens.

        Args:
            spider: The Scrapy spider instance.
        """
        # TODO: Implement in F-006
        pass

    def process_item(self, item: dict, spider: Spider) -> dict:  # noqa: ARG002
        """Store item to database.

        Args:
            item: The Scrapy item with _huginn_collected_item.
            spider: The Scrapy spider instance (unused but required by Scrapy API).

        Returns:
            The item.
        """
        # TODO: Implement in F-006
        return item

    def close_spider(self, spider: Spider) -> None:
        """Update run status and close database connection.

        Args:
            spider: The Scrapy spider instance.
        """
        # TODO: Implement in F-006
        pass
