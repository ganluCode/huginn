"""Tests for V2EX Spider."""

import json
from pathlib import Path

import pytest
from scrapy.http import JsonResponse

from huginn.core.constants import Category


@pytest.fixture
def hot_topics_fixture():
    """Load the V2EX hot topics fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "v2ex_hot.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def spider():
    """Create a V2EXSpider instance."""
    from huginn.scrapy.spiders.tech.v2ex import V2EXSpider

    return V2EXSpider()


class TestV2EXSpider:
    """Test V2EXSpider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "v2ex"
        assert spider.source_category == Category.TECH

    def test_spider_custom_settings(self, spider):
        """Spider should have custom_settings with DOWNLOAD_DELAY and Accept header."""
        assert "DOWNLOAD_DELAY" in spider.custom_settings
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1

        assert "DEFAULT_REQUEST_HEADERS" in spider.custom_settings
        headers = spider.custom_settings["DEFAULT_REQUEST_HEADERS"]
        assert "Accept" in headers or "accept" in headers

    def test_start_requests_yields_one_request(self, spider):
        """start_requests should yield a single request to hot topics API."""
        requests = list(spider.start_requests())
        assert len(requests) == 1
        assert "v2ex.com/api" in requests[0].url
        assert requests[0].callback == spider.parse

    def test_parse_normal_case(self, spider, hot_topics_fixture):
        """parse should extract all fields correctly from JSON array."""
        url = "https://www.v2ex.com/api/topics/hot.json"
        response = JsonResponse(url, request=None, body=json.dumps(hot_topics_fixture).encode())

        items = list(spider.parse(response))
        assert len(items) == 3

        # Verify first item
        item = items[0]
        assert item["_huginn_source"] == "v2ex"
        assert item["_huginn_category"] == Category.TECH
        assert item["title"] == "如何优化 Python 爬虫的性能"
        assert item["url"] == "https://www.v2ex.com/t/123456"
        assert item["content"] == "最近在写爬虫，发现性能瓶颈，有什么好的优化方案吗？"
        assert item["author"] == "python_dev"
        assert item["node"] == "Python"
        assert item["replies"] == 23
        assert item["created_at"] == 1678886400

    def test_parse_empty_json_array(self, spider):
        """parse with empty JSON array should yield zero items."""
        url = "https://www.v2ex.com/api/topics/hot.json"
        response = JsonResponse(url, request=None, body=b"[]")

        items = list(spider.parse(response))
        assert len(items) == 0

    def test_parse_field_mapping(self, spider, hot_topics_fixture):
        """parse should correctly map member.username to author and node.title to node."""
        url = "https://www.v2ex.com/api/topics/hot.json"
        response = JsonResponse(url, request=None, body=json.dumps(hot_topics_fixture).encode())

        items = list(spider.parse(response))

        # Verify field mapping for first item
        item = items[0]
        assert item["author"] == hot_topics_fixture[0]["member"]["username"]
        assert item["node"] == hot_topics_fixture[0]["node"]["title"]

        # Verify field mapping for second item
        item = items[1]
        assert item["author"] == hot_topics_fixture[1]["member"]["username"]
        assert item["node"] == hot_topics_fixture[1]["node"]["title"]

    def test_parse_calls_make_item(self, spider, hot_topics_fixture):
        """parse should use make_item to create items."""
        url = "https://www.v2ex.com/api/topics/hot.json"
        response = JsonResponse(url, request=None, body=json.dumps(hot_topics_fixture).encode())

        items = list(spider.parse(response))
        assert len(items) == 3

        # Verify the item structure matches what make_item produces
        item = items[0]
        assert "_huginn_source" in item
        assert "_huginn_category" in item

    def test_spider_inherits_from_base_spider(self, spider):
        """V2EXSpider should inherit from BaseSpider."""
        from huginn.scrapy.base_spider import BaseSpider

        assert isinstance(spider, BaseSpider)
        assert hasattr(spider, "make_item")
