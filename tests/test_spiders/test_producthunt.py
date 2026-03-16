"""Tests for ProductHunt Spider."""

from pathlib import Path

import pytest
from scrapy.http import HtmlResponse

from huginn.core.constants import Category


@pytest.fixture
def producthunt_html_fixture():
    """Load the ProductHunt HTML fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "producthunt.html"
    return fixture_path.read_text()


@pytest.fixture
def producthunt_empty_html_fixture():
    """Load the empty ProductHunt HTML fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "producthunt_empty.html"
    return fixture_path.read_text()


@pytest.fixture
def spider():
    """Create a ProductHuntSpider instance."""
    from huginn.scrapy.spiders.tech.producthunt import ProductHuntSpider

    return ProductHuntSpider()


class TestProductHuntSpider:
    """Test ProductHuntSpider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "producthunt"
        assert spider.source_category == Category.TECH

    def test_start_requests_yields_one_request(self, spider):
        """start_requests should yield a single request to ProductHunt homepage."""
        requests = list(spider.start_requests())
        assert len(requests) == 1
        assert requests[0].url == "https://www.producthunt.com/"
        assert requests[0].callback == spider.parse

    def test_parse_normal_case(self, spider, producthunt_html_fixture):
        """parse should extract all fields correctly from HTML."""
        url = "https://www.producthunt.com/"
        response = HtmlResponse(url, request=None, body=producthunt_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 3

        # Verify first item (all fields present)
        item = items[0]
        assert item["_huginn_source"] == "producthunt"
        assert item["_huginn_category"] == Category.TECH
        assert item["title"] == "AI Assistant Pro"
        assert item["url"] == "/posts/ai-assistant-pro"
        assert item["tagline"] == "Your intelligent coding companion powered by GPT-4"
        assert item["votes"] == "428"
        assert item["topics"] == ["Productivity", "Developer Tools"]

    def test_parse_missing_fields(self, spider, producthunt_html_fixture):
        """parse should handle missing tagline, votes, topics gracefully."""
        url = "https://www.producthunt.com/"
        response = HtmlResponse(url, request=None, body=producthunt_html_fixture.encode())

        items = list(spider.parse(response))

        # Second product missing topics and tagline
        item = items[1]
        assert item["title"] == "Fast CMS"
        assert item["url"] == "/posts/fast-cms"
        assert item["tagline"] is None
        assert item["votes"] == "156"
        assert item["topics"] is None

        # Third product missing votes
        item = items[2]
        assert item["title"] == "Design Tool"
        assert item["url"] == "/posts/design-tool"
        assert item["tagline"] == "Beautiful designs in minutes"
        assert item["votes"] is None
        assert item["topics"] == ["Design"]

    def test_parse_empty_product_list(self, spider, producthunt_empty_html_fixture):
        """parse with empty product list should yield zero items."""
        url = "https://www.producthunt.com/"
        response = HtmlResponse(url, request=None, body=producthunt_empty_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 0

    def test_parse_calls_make_item(self, spider, producthunt_html_fixture):
        """parse should use make_item to create items."""
        url = "https://www.producthunt.com/"
        response = HtmlResponse(url, request=None, body=producthunt_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 3

        # Verify the item structure matches what make_item produces
        item = items[0]
        assert "_huginn_source" in item
        assert "_huginn_category" in item

    def test_spider_inherits_from_base_spider(self, spider):
        """ProductHuntSpider should inherit from BaseSpider."""
        from huginn.scrapy.base_spider import BaseSpider

        assert isinstance(spider, BaseSpider)
        assert hasattr(spider, "make_item")
