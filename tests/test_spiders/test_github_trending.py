"""Tests for GitHub Trending Spider."""

from pathlib import Path

import pytest
from scrapy.http import HtmlResponse

from huginn.core.constants import Category
from huginn.scrapy.spiders.tech.github_trending import GitHubTrendingSpider


@pytest.fixture
def trending_fixture():
    """Load the GitHub trending HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "github_trending.html"
    return fixture_path.read_text()


@pytest.fixture
def spider():
    """Create a GitHubTrendingSpider instance."""
    return GitHubTrendingSpider()


class TestGitHubTrendingSpider:
    """Test GitHubTrendingSpider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "github_trending"
        assert spider.source_category == Category.TECH

    def test_custom_settings(self, spider):
        """Spider should have correct custom_settings."""
        assert spider.custom_settings["ROBOTSTXT_OBEY"] is False
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1

    def test_parse_normal(self, spider, trending_fixture):
        """parse should extract all fields correctly for normal entries."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))
        # Should have 3 entries from fixture
        assert len(items) == 3

        # Check first entry (vercel/next.js)
        item1 = items[0]
        assert item1["title"] == "vercel/next.js"
        assert item1["url"] == "https://github.com/vercel/next.js"
        assert item1["description"] == "The React Framework - used to build this and many other websites"
        assert item1["language"] == "JavaScript"
        assert item1["stars_total"] == "123,456"  # Raw string
        assert item1["stars_today"] == "1,234 stars today"  # Raw string with text
        assert item1["forks"] == "23,456"  # Raw string

        # Check third entry (tensorflow/tensorflow)
        item3 = items[2]
        assert item3["title"] == "tensorflow/tensorflow"
        assert item3["url"] == "https://github.com/tensorflow/tensorflow"
        assert item3["description"] == "An Open Source Machine Learning Framework for Everyone"
        assert item3["language"] == "C++"

    def test_parse_missing_language(self, spider, trending_fixture):
        """parse should handle missing language (output None)."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))
        # Second entry (openai/openai-cookbook) has no language
        item2 = items[1]
        assert item2["title"] == "openai/openai-cookbook"
        assert item2["language"] is None

    def test_parse_missing_description(self, spider, trending_fixture):
        """parse should handle missing description (output None)."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))
        # Second entry (openai/openai-cookbook) has no description
        item2 = items[1]
        assert item2["title"] == "openai/openai-cookbook"
        assert item2["description"] is None

    def test_parse_stars_raw_string(self, spider, trending_fixture):
        """stars_total and stars_today should be raw strings, not converted."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))
        item1 = items[0]

        # Should be strings, not integers
        assert isinstance(item1["stars_total"], str)
        assert isinstance(item1["stars_today"], str)
        assert isinstance(item1["forks"], str)

        # Verify raw values
        assert item1["stars_total"] == "123,456"
        assert item1["stars_today"] == "1,234 stars today"
        assert item1["forks"] == "23,456"

    def test_parse_empty_page(self, spider, caplog):
        """parse with no matching selectors should yield 0 items and log WARNING."""
        html = "<html><body><p>No trending items here</p></body></html>"
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=html.encode())

        items = list(spider.parse(response))
        assert len(items) == 0

        # Should log a warning
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_parse_huginn_metadata(self, spider, trending_fixture):
        """Items should include Huginn metadata."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) > 0

        item = items[0]
        assert item["_huginn_source"] == "github_trending"
        assert item["_huginn_category"] == Category.TECH

    def test_parse_title_format(self, spider, trending_fixture):
        """Title should be in 'owner/repo' format."""
        url = "https://github.com/trending"
        response = HtmlResponse(url, request=None, body=trending_fixture.encode())

        items = list(spider.parse(response))

        # All titles should have owner/repo format
        for item in items:
            title = item["title"]
            assert "/" in title
            # Should not have leading slash from href
            assert not title.startswith("/")
