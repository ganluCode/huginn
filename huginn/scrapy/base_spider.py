"""Base Spider class for Huginn Scrapy spiders.

This module provides BaseSpider, a base class for all Scrapy spiders in Huginn.
It adds common functionality like automatic metadata injection and item creation.
"""

from scrapy import Spider


class BaseSpider(Spider):
    """Base Spider class with Huginn-specific functionality.

    All Huginn spiders should inherit from this class. It provides:
    - source_category: A class attribute for categorizing data sources
    - make_item(): A method to create items with automatic Huginn metadata

    Example:
        class MySpider(BaseSpider):
            name = "my_spider"
            source_category = "tech"

            def parse(self, response):
                yield self.make_item(title="Example", url="http://example.com")
    """

    # Class attribute for data source categorization
    # Subclasses should override this with appropriate category:
    # "finance", "social", "tech", "market", etc.
    source_category: str | None = None

    def make_item(self, **kwargs) -> dict:
        """Create an item dict with automatic Huginn metadata.

        This method creates a dictionary containing:
        - _huginn_source: The spider's name (auto-filled, can be overridden)
        - _huginn_category: The spider's source_category (auto-filled, can be overridden)
        - Any additional fields passed as kwargs

        Args:
            **kwargs: Field names and values for the item. Can include:
                - Business fields (title, url, content, etc.)
                - _huginn_source to override the default spider name
                - _huginn_category to override the default source_category

        Returns:
            A dictionary with all provided fields plus Huginn metadata.

        Example:
            >>> spider = BaseSpider(name="test")
            >>> spider.source_category = "tech"
            >>> item = spider.make_item(title="Hello", url="http://example.com")
            >>> item["_huginn_source"]
            'test'
            >>> item["_huginn_category"]
            'tech'
            >>> item["title"]
            'Hello'

            >>> # Override auto-filled values
            >>> item = spider.make_item(_huginn_source="custom", title="Hello")
            >>> item["_huginn_source"]
            'custom'
        """
        # Start with auto-filled Huginn metadata
        item = {
            "_huginn_source": self.name,
            "_huginn_category": self.source_category,
        }

        # Merge kwargs, allowing them to override auto-filled values
        item.update(kwargs)

        return item
