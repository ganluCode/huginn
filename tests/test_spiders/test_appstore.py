"""Tests for App Store Spider."""

import json
import logging
from pathlib import Path

import pytest
from scrapy.http import JsonResponse, Request

from huginn.core.constants import Category
from huginn.scrapy.spiders.market.appstore import AppstoreSpider


@pytest.fixture
def spider():
    """Create an AppstoreSpider instance."""
    return AppstoreSpider()


@pytest.fixture
def fixture_data():
    """Load the appstore_top_free fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "appstore_top_free.json"
    return json.loads(fixture_path.read_text())


def _make_json_response(url, data, chart="top-free", country="cn"):
    """Helper to create a JsonResponse for testing."""
    request = Request(url)
    return JsonResponse(url, request=request, body=json.dumps(data).encode())


class TestAppstoreSpiderAttributes:
    def test_name(self, spider):
        assert spider.name == "appstore"

    def test_source_category(self, spider):
        assert spider.source_category == Category.MARKET


class TestAppstoreSpiderStartRequests:
    def test_yields_request_per_target(self, spider):
        from huginn.scrapy.spiders.market.appstore import _DEFAULT_TARGETS

        requests = list(spider.start_requests())
        assert len(requests) == len(_DEFAULT_TARGETS)

    def test_request_url_format(self, spider):
        from huginn.scrapy.spiders.market.appstore import _DEFAULT_TARGETS

        requests = list(spider.start_requests())
        for req, target in zip(requests, _DEFAULT_TARGETS):
            expected = (
                f"https://rss.applemarketingtools.com/api/v2"
                f"/{target['country']}/apps/{target['chart']}/{target['limit']}/apps.json"
            )
            assert req.url == expected


class TestAppstoreSpiderParse:
    def test_normal_parse(self, spider, fixture_data):
        """test_normal_parse: 5 items are yielded, first item has rank=1 and correct fields."""
        url = "https://rss.applemarketingtools.com/api/v2/cn/apps/top-free/25/apps.json"
        response = _make_json_response(url, fixture_data)
        items = list(spider.parse(response, chart="top-free", country="cn"))

        assert len(items) == 5

        first = items[0]
        assert first["rank"] == 1
        assert first["title"] == "Instagram"
        assert first["app_id"] == "389801252"
        assert first["artist"] == "Instagram, Inc."
        assert first["chart"] == "top-free"
        assert first["country"] == "cn"
        assert first["_huginn_source"] == "appstore"
        assert first["_huginn_category"] == Category.MARKET

    def test_empty_genres(self, spider, fixture_data):
        """test_empty_genres: App with empty genres list has category=None."""
        url = "https://rss.applemarketingtools.com/api/v2/cn/apps/top-free/25/apps.json"
        response = _make_json_response(url, fixture_data)
        items = list(spider.parse(response, chart="top-free", country="cn"))

        # Facebook (index 3) has genres=[]
        facebook_item = items[3]
        assert facebook_item["title"] == "Facebook"
        assert facebook_item["category"] is None

    def test_empty_results(self, spider, caplog):
        """test_empty_results: Empty results list yields no items and logs WARNING."""
        url = "https://rss.applemarketingtools.com/api/v2/cn/apps/top-free/25/apps.json"
        data = {"feed": {"results": []}}
        response = _make_json_response(url, data)

        with caplog.at_level(logging.WARNING, logger="huginn.scrapy.spiders.market.appstore"):
            items = list(spider.parse(response, chart="top-free", country="cn"))

        assert items == []
        assert any(record.levelno >= logging.WARNING for record in caplog.records)

    def test_rank_increments(self, spider, fixture_data):
        """Ranks start at 1 and increment sequentially."""
        url = "https://rss.applemarketingtools.com/api/v2/cn/apps/top-free/25/apps.json"
        response = _make_json_response(url, fixture_data)
        items = list(spider.parse(response, chart="top-free", country="cn"))

        for i, item in enumerate(items, start=1):
            assert item["rank"] == i
