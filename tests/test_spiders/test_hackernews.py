"""Tests for HackerNews Spider."""

import json
from pathlib import Path

import pytest
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.spiders.tech.hackernews import HackerNewsSpider


@pytest.fixture
def topstories_fixture():
    """Load the topstories fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "hackernews_topstories.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def item_fixture():
    """Load the item fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "hackernews_item.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def spider():
    """Create a HackerNewsSpider instance."""
    return HackerNewsSpider()


class TestHackerNewsSpider:
    """Test HackerNewsSpider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "hackernews"
        assert spider.source_category == Category.TECH

    def test_start_requests_yields_one_request(self, spider):
        """start_requests should yield a single request to topstories URL."""
        requests = list(spider.start_requests())
        assert len(requests) == 1
        assert requests[0].url == HackerNewsSpider.TOPSTORIES_URL
        assert requests[0].callback == spider.parse

    def test_parse_yields_requests_for_top_30_stories(self, spider, topstories_fixture):
        """parse should yield a request for each of the first 30 story IDs."""
        # Create a fake JSON response
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = JsonResponse(url, request=None, body=json.dumps(topstories_fixture).encode())

        # Get the yielded requests
        requests = list(spider.parse(response))

        # Fixture has 5 IDs, but spider limits to 30, so expect 5
        expected_count = min(len(topstories_fixture), HackerNewsSpider.MAX_STORIES)
        assert len(requests) == expected_count

        # Verify each request has the correct URL and callback
        for i, req in enumerate(requests):
            expected_id = topstories_fixture[i]
            expected_url = f"https://hacker-news.firebaseio.com/v0/item/{expected_id}.json"
            assert req.url == expected_url
            assert req.callback == spider.parse_story

    def test_parse_empty_topstories_yields_no_requests(self, spider):
        """parse with empty list should yield zero requests."""
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = JsonResponse(url, request=None, body=b"[]")

        requests = list(spider.parse(response))
        assert len(requests) == 0

    def test_parse_story_normal_case(self, spider, item_fixture):
        """parse_story should extract all fields correctly."""
        story = item_fixture["normal"]
        url = f"https://hacker-news.firebaseio.com/v0/item/{story['id']}.json"
        response = JsonResponse(url, request=None, body=json.dumps(story).encode())

        items = list(spider.parse_story(response))
        assert len(items) == 1

        item = items[0]
        # Verify Huginn metadata
        assert item["_huginn_source"] == "hackernews"
        assert item["_huginn_category"] == Category.TECH

        # Verify business fields
        assert item["hn_id"] == 1001
        assert item["title"] == "Show HN: I built a tool for data collection"
        assert item["url"] == "https://github.com/example/data-tool"
        assert item["score"] == 42
        assert item["author"] == "developer123"
        assert item["comments"] == 15

    def test_parse_story_missing_url(self, spider, item_fixture):
        """parse_story should handle missing url field (output None)."""
        story = item_fixture["missing_url"]
        url = f"https://hacker-news.firebaseio.com/v0/item/{story['id']}.json"
        response = JsonResponse(url, request=None, body=json.dumps(story).encode())

        items = list(spider.parse_story(response))
        assert len(items) == 1

        item = items[0]
        assert item["url"] is None

    def test_parse_story_missing_descendants(self, spider, item_fixture):
        """parse_story should default comments to 0 when descendants missing."""
        story = item_fixture["missing_descendants"]
        url = f"https://hacker-news.firebaseio.com/v0/item/{story['id']}.json"
        response = JsonResponse(url, request=None, body=json.dumps(story).encode())

        items = list(spider.parse_story(response))
        assert len(items) == 1

        item = items[0]
        assert item["comments"] == 0

    def test_parse_story_null_response(self, spider):
        """parse_story should yield nothing when response body is null."""
        url = "https://hacker-news.firebaseio.com/v0/item/99999.json"
        response = JsonResponse(url, request=None, body=b"null")

        items = list(spider.parse_story(response))
        assert len(items) == 0

    def test_parse_story_calls_make_item(self, spider, item_fixture):
        """parse_story should use make_item to create items."""
        story = item_fixture["normal"]
        url = f"https://hacker-news.firebaseio.com/v0/item/{story['id']}.json"
        response = JsonResponse(url, request=None, body=json.dumps(story).encode())

        items = list(spider.parse_story(response))
        assert len(items) == 1

        # Verify the item structure matches what make_item produces
        item = items[0]
        assert "_huginn_source" in item
        assert "_huginn_category" in item
        # All other keys should be business fields
        assert "hn_id" in item
        assert "title" in item

    def test_max_stories_limit(self):
        """Spider should have MAX_STORIES = 30."""
        assert HackerNewsSpider.MAX_STORIES == 30
