"""Tests for 36kr Spider."""

from pathlib import Path

import pytest
from scrapy.http import HtmlResponse

from huginn.core.constants import Category


@pytest.fixture
def kr36_html_fixture():
    """Load the 36kr HTML fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "kr36_newsflash.html"
    return fixture_path.read_text()


@pytest.fixture
def kr36_empty_html_fixture():
    """Load the empty 36kr HTML fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "kr36_empty.html"
    return fixture_path.read_text()


@pytest.fixture
def spider():
    """Create a Kr36Spider instance."""
    from huginn.scrapy.spiders.news.kr36 import Kr36Spider

    return Kr36Spider()


class TestKr36Spider:
    """Test Kr36Spider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "kr36"
        assert spider.source_category == Category.NEWS

    def test_start_requests_yields_one_request(self, spider):
        """start_requests should yield a single request to 36kr newsflashes page."""
        requests = list(spider.start_requests())
        assert len(requests) == 1
        assert requests[0].url == "https://36kr.com/newsflashes"
        assert requests[0].callback == spider.parse

    def test_parse_normal_case(self, spider, kr36_html_fixture):
        """parse should extract all fields correctly from HTML."""
        url = "https://36kr.com/newsflashes"
        response = HtmlResponse(url, request=None, body=kr36_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 4

        # Verify first item (all fields present)
        item = items[0]
        assert item["_huginn_source"] == "kr36"
        assert item["_huginn_category"] == Category.NEWS
        assert item["title"] == '字节跳动发布 AI 大模型"豆包"，支持多模态交互'
        assert item["url"] == "/newsflash/12345"
        assert item["summary"] == '字节跳动正式发布自研 AI 大模型"豆包"，支持文本、图像、语音多模态交互，将应用于抖音、今日头条等产品。'
        assert item["published_at"] == "2026-03-17T10:30:00+08:00"

    def test_parse_missing_fields(self, spider, kr36_html_fixture):
        """parse should handle missing summary and published_at gracefully."""
        url = "https://36kr.com/newsflashes"
        response = HtmlResponse(url, request=None, body=kr36_html_fixture.encode())

        items = list(spider.parse(response))

        # Third item missing summary
        item = items[2]
        assert item["title"] == "OpenAI 推出 GPT-5 预览版"
        assert item["url"] == "/newsflash/12347"
        assert item["summary"] is None
        assert item["published_at"] == "2026-03-17T08:00:00+08:00"

        # Fourth item missing published_at
        item = items[3]
        assert item["title"] == "小米汽车宣布进军欧洲市场"
        assert item["url"] == "/newsflash/12348"
        assert item["summary"] == "小米汽车宣布将于今年内进入欧洲市场，首批销售国家包括德国、法国、意大利。"
        assert item["published_at"] is None

    def test_parse_empty_newsflash_list(self, spider, kr36_empty_html_fixture):
        """parse with empty newsflash list should yield zero items."""
        url = "https://36kr.com/newsflashes"
        response = HtmlResponse(url, request=None, body=kr36_empty_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 0

    def test_parse_calls_make_item(self, spider, kr36_html_fixture):
        """parse should use make_item to create items."""
        url = "https://36kr.com/newsflashes"
        response = HtmlResponse(url, request=None, body=kr36_html_fixture.encode())

        items = list(spider.parse(response))
        assert len(items) == 4

        # Verify the item structure matches what make_item produces
        item = items[0]
        assert "_huginn_source" in item
        assert "_huginn_category" in item

    def test_spider_inherits_from_base_spider(self, spider):
        """Kr36Spider should inherit from BaseSpider."""
        from huginn.scrapy.base_spider import BaseSpider

        assert isinstance(spider, BaseSpider)
        assert hasattr(spider, "make_item")

    def test_custom_settings_download_delay(self, spider):
        """Spider should have DOWNLOAD_DELAY in custom_settings."""
        assert "DOWNLOAD_DELAY" in spider.custom_settings
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 1
