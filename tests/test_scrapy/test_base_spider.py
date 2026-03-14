"""Test BaseSpider implementation (F-003)."""

from scrapy import Spider

from huginn.scrapy.base_spider import BaseSpider


class TestBaseSpider:
    """Verify BaseSpider provides the expected interface."""

    def test_base_spider_inherits_from_scrapy_spider(self):
        """BaseSpider should be a subclass of scrapy.Spider."""
        assert issubclass(BaseSpider, Spider)

    def test_source_category_class_attribute(self):
        """source_category should be a class attribute that can be overridden."""
        _ = BaseSpider(name="test_spider")
        # Default value should be None (or some default)
        # The key point is that it's a class attribute
        assert hasattr(BaseSpider, "source_category")

    def test_source_category_can_be_overridden(self):
        """Subclasses should be able to override source_category."""
        class CustomSpider(BaseSpider):
            name = "custom_spider"
            source_category = "tech"

        spider = CustomSpider()
        assert spider.source_category == "tech"

    def test_make_item_with_fields(self):
        """make_item should include business fields and _huginn_ metadata."""
        spider = BaseSpider(name="test_spider")
        spider.source_category = "finance"

        item = spider.make_item(title="Test Title", url="http://example.com")

        assert item["_huginn_source"] == "test_spider"
        assert item["_huginn_category"] == "finance"
        assert item["title"] == "Test Title"
        assert item["url"] == "http://example.com"

    def test_make_item_without_fields(self):
        """make_item without arguments should return dict with only _huginn_ fields."""
        spider = BaseSpider(name="test_spider")
        spider.source_category = "tech"

        item = spider.make_item()

        assert item["_huginn_source"] == "test_spider"
        assert item["_huginn_category"] == "tech"
        # Should only have the two metadata fields
        assert set(item.keys()) == {"_huginn_source", "_huginn_category"}

    def test_make_item_kwargs_override_auto_values(self):
        """kwargs should override auto-filled _huginn_ values."""
        spider = BaseSpider(name="test_spider")
        spider.source_category = "tech"

        item = spider.make_item(_huginn_source="custom_source", title="Test")

        # kwargs should override the auto-filled value
        assert item["_huginn_source"] == "custom_source"
        assert item["_huginn_category"] == "tech"
        assert item["title"] == "Test"

    def test_make_item_with_all_huginn_fields_override(self):
        """All _huginn_ fields can be overridden via kwargs."""
        spider = BaseSpider(name="test_spider")
        spider.source_category = "original_category"

        item = spider.make_item(
            _huginn_source="override_source",
            _huginn_category="override_category",
        )

        assert item["_huginn_source"] == "override_source"
        assert item["_huginn_category"] == "override_category"

    def test_make_item_mixed_fields(self):
        """make_item should handle mix of _huginn_ and business fields."""
        spider = BaseSpider(name="news_spider")
        spider.source_category = "news"

        item = spider.make_item(
            headline="Breaking News",
            author="John Doe",
            timestamp="2026-03-15T00:00:00Z",
        )

        assert item["_huginn_source"] == "news_spider"
        assert item["_huginn_category"] == "news"
        assert item["headline"] == "Breaking News"
        assert item["author"] == "John Doe"
        assert item["timestamp"] == "2026-03-15T00:00:00Z"
