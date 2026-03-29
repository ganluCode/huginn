"""Tests for Google Trends Spider."""

import json
import logging
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests
from scrapy.http import Request, Response

from huginn.core.constants import Category
from huginn.scrapy.spiders.trends.google_trends import (
    GOOGLE_TRENDS_REGIONS,
    GoogleTrendsSpider,
    _MAX_RETRIES,
)


@pytest.fixture
def spider():
    """Create a GoogleTrendsSpider instance with a mock pytrends client."""
    s = GoogleTrendsSpider()
    s._pytrends = MagicMock()
    return s


@pytest.fixture
def fixture_terms():
    """Load the google_trends_daily fixture data (list of trending terms)."""
    fixture_path = Path(__file__).parent / "fixtures" / "google_trends_daily.json"
    return json.loads(fixture_path.read_text())


def _make_response(spider, region):
    """Helper to create a minimal Scrapy Response with region in meta."""
    url = f"https://trends.google.com/trends/trendingsearches/daily?geo={region}"
    request = Request(url, meta={"region": region})
    return Response(url=url, request=request)


class TestGoogleTrendsSpiderAttributes:
    def test_name(self, spider):
        assert spider.name == "google_trends"

    def test_source_category(self, spider):
        assert spider.source_category == Category.TRENDS


class TestGoogleTrendsSpiderStartRequests:
    def test_yields_one_request_per_default_region(self):
        with patch("huginn.scrapy.spiders.trends.google_trends.TrendReq"):
            s = GoogleTrendsSpider()
        requests_list = list(s.start_requests())
        assert len(requests_list) == len(GOOGLE_TRENDS_REGIONS)

    def test_request_meta_contains_region(self):
        with patch("huginn.scrapy.spiders.trends.google_trends.TrendReq"):
            s = GoogleTrendsSpider()
        requests_list = list(s.start_requests())
        regions = [req.meta["region"] for req in requests_list]
        assert regions == list(GOOGLE_TRENDS_REGIONS)

    def test_request_callback_is_parse(self):
        with patch("huginn.scrapy.spiders.trends.google_trends.TrendReq"):
            s = GoogleTrendsSpider()
        requests_list = list(s.start_requests())
        for req in requests_list:
            assert req.callback == s.parse

    def test_instantiates_trendreq_with_correct_args(self):
        with patch("huginn.scrapy.spiders.trends.google_trends.TrendReq") as mock_cls:
            s = GoogleTrendsSpider()
            list(s.start_requests())
        mock_cls.assert_called_once_with(hl="zh-CN", tz=480)


class TestGoogleTrendsSpiderParseNormal:
    def test_yields_correct_item_count(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        items = list(spider.parse(response))

        assert len(items) == len(fixture_terms)

    def test_item_title_matches_fixture(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        items = list(spider.parse(response))

        for item, term in zip(items, fixture_terms):
            assert item["title"] == term

    def test_item_rank_starts_at_one(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        items = list(spider.parse(response))

        assert items[0]["rank"] == 1
        for i, item in enumerate(items):
            assert item["rank"] == i + 1

    def test_item_region_matches_request_region(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "united_states")
        items = list(spider.parse(response))

        for item in items:
            assert item["region"] == "united_states"

    def test_item_url_is_google_search_link(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        items = list(spider.parse(response))

        for item, term in zip(items, fixture_terms):
            expected_url = f"https://www.google.com/search?q={urllib.parse.quote(term)}"
            assert item["url"] == expected_url

    def test_item_huginn_metadata(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        items = list(spider.parse(response))

        for item in items:
            assert item["_huginn_source"] == "google_trends"
            assert item["_huginn_category"] == Category.TRENDS

    def test_pytrends_called_with_region(self, spider, fixture_terms):
        df = pd.DataFrame(fixture_terms)
        spider._pytrends.trending_searches.return_value = df

        response = _make_response(spider, "china")
        list(spider.parse(response))

        spider._pytrends.trending_searches.assert_called_once_with(pn="china")


class TestGoogleTrendsSpiderParseEmpty:
    def test_empty_dataframe_yields_no_items(self, spider, caplog):
        spider._pytrends.trending_searches.return_value = pd.DataFrame()

        response = _make_response(spider, "china")
        with caplog.at_level(logging.WARNING, logger="huginn.scrapy.spiders.trends.google_trends"):
            items = list(spider.parse(response))

        assert items == []

    def test_empty_dataframe_logs_warning(self, spider, caplog):
        spider._pytrends.trending_searches.return_value = pd.DataFrame()

        response = _make_response(spider, "china")
        with caplog.at_level(logging.WARNING, logger="huginn.scrapy.spiders.trends.google_trends"):
            list(spider.parse(response))

        assert any(record.levelno >= logging.WARNING for record in caplog.records)


class TestGoogleTrendsSpiderRetryOnTimeout:
    def test_timeout_yields_no_items(self, spider):
        spider._pytrends.trending_searches.side_effect = requests.exceptions.Timeout("timeout")

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            items = list(spider.parse(response))

        assert items == []

    def test_timeout_retries_max_retries_times(self, spider):
        spider._pytrends.trending_searches.side_effect = requests.exceptions.Timeout("timeout")

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            list(spider.parse(response))

        assert spider._pytrends.trending_searches.call_count == _MAX_RETRIES + 1

    def test_timeout_sleeps_between_retries(self, spider):
        spider._pytrends.trending_searches.side_effect = requests.exceptions.Timeout("timeout")

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            list(spider.parse(response))

        assert mock_time.sleep.call_count == _MAX_RETRIES

    def test_timeout_logs_error(self, spider, caplog):
        spider._pytrends.trending_searches.side_effect = requests.exceptions.Timeout("timeout")

        with patch("huginn.scrapy.spiders.trends.google_trends.time"):
            response = _make_response(spider, "china")
            with caplog.at_level(logging.ERROR, logger="huginn.scrapy.spiders.trends.google_trends"):
                list(spider.parse(response))

        assert any(record.levelno >= logging.ERROR for record in caplog.records)


def _make_429_error():
    """Create a TooManyRequestsError with required constructor arguments."""
    from pytrends.exceptions import TooManyRequestsError

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    return TooManyRequestsError("429 Too Many Requests", mock_resp)


class TestGoogleTrendsSpiderRetryOn429:
    def test_429_yields_no_items(self, spider):
        spider._pytrends.trending_searches.side_effect = _make_429_error()

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            items = list(spider.parse(response))

        assert items == []

    def test_429_retries_max_retries_times(self, spider):
        spider._pytrends.trending_searches.side_effect = _make_429_error()

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            list(spider.parse(response))

        assert spider._pytrends.trending_searches.call_count == _MAX_RETRIES + 1

    def test_429_sleeps_between_retries(self, spider):
        spider._pytrends.trending_searches.side_effect = _make_429_error()

        with patch("huginn.scrapy.spiders.trends.google_trends.time") as mock_time:
            mock_time.sleep = MagicMock()
            response = _make_response(spider, "china")
            list(spider.parse(response))

        assert mock_time.sleep.call_count == _MAX_RETRIES

    def test_429_logs_error(self, spider, caplog):
        spider._pytrends.trending_searches.side_effect = _make_429_error()

        with patch("huginn.scrapy.spiders.trends.google_trends.time"):
            response = _make_response(spider, "china")
            with caplog.at_level(logging.ERROR, logger="huginn.scrapy.spiders.trends.google_trends"):
                list(spider.parse(response))

        assert any(record.levelno >= logging.ERROR for record in caplog.records)

    def test_429_does_not_raise(self, spider):
        spider._pytrends.trending_searches.side_effect = _make_429_error()

        with patch("huginn.scrapy.spiders.trends.google_trends.time"):
            response = _make_response(spider, "china")
            # Should not raise
            list(spider.parse(response))
