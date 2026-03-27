"""Tests for Reddit Spider."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from scrapy.http import JsonResponse, Request, Response

from huginn.core.constants import Category
from huginn.scrapy.spiders.community.reddit import SELFTEXT_MAX_LENGTH, RedditSpider


@pytest.fixture
def spider():
    """Create a RedditSpider instance with default settings."""
    return RedditSpider()


@pytest.fixture
def fixture_data():
    """Load the reddit_hot fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "reddit_hot.json"
    return json.loads(fixture_path.read_text())


def _make_json_response(spider, url, data):
    """Helper to create a JsonResponse for testing."""
    request = Request(url)
    return JsonResponse(url, request=request, body=json.dumps(data).encode())


class TestRedditSpiderAttributes:
    def test_name(self, spider):
        assert spider.name == "reddit"

    def test_source_category(self, spider):
        assert spider.source_category == Category.COMMUNITY

    def test_custom_settings_download_delay(self, spider):
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1

    def test_custom_settings_user_agent(self, spider):
        headers = spider.custom_settings["DEFAULT_REQUEST_HEADERS"]
        assert headers.get("User-Agent") == "huginn/1.0"


class TestRedditSpiderStartRequests:
    def test_yields_request_per_subreddit(self, spider):
        requests = list(spider.start_requests())
        assert len(requests) == len(spider._default_subreddits)

    def test_request_url_format(self, spider):
        requests = list(spider.start_requests())
        limit = spider._default_limit
        for req, subreddit in zip(requests, spider._default_subreddits):
            expected = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            assert req.url == expected

    def test_requests_have_errback(self, spider):
        requests = list(spider.start_requests())
        for req in requests:
            assert req.errback == spider.handle_error


class TestRedditSpiderParse:
    def test_parse_normal_post(self, spider, fixture_data):
        """test_parse_normal_post: title/url/subreddit/score/comments/author/created_at are correct."""
        url = "https://www.reddit.com/r/SideProject/hot.json?limit=25"
        response = _make_json_response(spider, url, fixture_data)
        items = list(spider.parse(response))

        # First post in fixture
        item = items[0]
        assert item["title"] == "I launched my SaaS and got 100 users in the first week"
        assert item["url"] == "https://www.reddit.com/r/SideProject/comments/abc123/i_launched_my_saas/"
        assert item["subreddit"] == "SideProject"
        assert item["score"] == 512
        assert item["comments"] == 87
        assert item["author"] == "indie_founder"
        assert item["created_at"] is not None
        assert "2024" in item["created_at"] or "T" in item["created_at"]

    def test_parse_yields_huginn_metadata(self, spider, fixture_data):
        url = "https://www.reddit.com/r/SideProject/hot.json?limit=25"
        response = _make_json_response(spider, url, fixture_data)
        items = list(spider.parse(response))
        assert len(items) > 0
        for item in items:
            assert item["_huginn_source"] == "reddit"
            assert item["_huginn_category"] == Category.COMMUNITY

    def test_parse_external_url(self, spider, fixture_data):
        """test_parse_external_url: external link post has non-None external_url."""
        url = "https://www.reddit.com/r/SideProject/hot.json?limit=25"
        response = _make_json_response(spider, url, fixture_data)
        items = list(spider.parse(response))

        # Second post is an external link (github.com URL)
        item = items[1]
        assert item["external_url"] is not None
        assert "github.com" in item["external_url"]
        # selftext is None or empty for external link post
        assert not item["selftext"]

    def test_selftext_truncated(self, spider, fixture_data):
        """test_selftext_truncated: selftext > 2000 chars is truncated to 2000."""
        url = "https://www.reddit.com/r/startups/hot.json?limit=25"
        response = _make_json_response(spider, url, fixture_data)
        items = list(spider.parse(response))

        # Fourth post has a very long selftext
        item = items[3]
        assert item["selftext"] is not None
        assert len(item["selftext"]) == SELFTEXT_MAX_LENGTH

    def test_deleted_author(self, spider, fixture_data):
        """test_deleted_author: post with author=[deleted] is yielded normally."""
        url = "https://www.reddit.com/r/entrepreneur/hot.json?limit=25"
        response = _make_json_response(spider, url, fixture_data)
        items = list(spider.parse(response))

        # Third post has author=[deleted]
        item = items[2]
        assert item["author"] == "[deleted]"

    def test_parse_empty_response(self, spider):
        """parse with no children should yield no items."""
        url = "https://www.reddit.com/r/SideProject/hot.json?limit=25"
        data = {"data": {"children": []}}
        response = _make_json_response(spider, url, data)
        items = list(spider.parse(response))
        assert items == []


class TestRedditSpiderErrback:
    def test_404_errback_logs_warning_and_does_not_raise(self, spider, caplog):
        """test_404_errback: 404 triggers handle_error, logs WARNING, no exception."""
        # Build a fake HTTP 404 failure
        from scrapy.http import Response as ScrapyResponse
        from scrapy.spidermiddlewares.httperror import HttpError
        from twisted.python.failure import Failure

        request = Request("https://www.reddit.com/r/nonexistent/hot.json")
        response = ScrapyResponse(
            url="https://www.reddit.com/r/nonexistent/hot.json",
            status=404,
            request=request,
        )
        http_error = HttpError(response, "Not Found")
        failure = Failure(http_error)

        with caplog.at_level(logging.WARNING, logger="huginn.scrapy.spiders.community.reddit"):
            # Should not raise
            result = spider.handle_error(failure)

        assert result is None
        assert any("WARNING" in record.levelname or record.levelno >= logging.WARNING
                   for record in caplog.records)
