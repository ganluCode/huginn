"""Tests for CoinGecko Spider."""

import json
from pathlib import Path

import pytest
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.spiders.finance.crypto_price import CoinGeckoSpider


@pytest.fixture
def markets_fixture():
    """Load the CoinGecko markets fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "coingecko_markets.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def spider():
    """Create a CoinGeckoSpider instance."""
    return CoinGeckoSpider()


class TestCoinGeckoSpider:
    """Test CoinGeckoSpider implementation."""

    def test_spider_name_and_category(self, spider):
        """Spider should have correct name and source_category."""
        assert spider.name == "crypto_price"
        assert spider.source_category == Category.FINANCE

    def test_custom_settings(self, spider):
        """Spider should have correct custom_settings."""
        assert spider.custom_settings["ROBOTSTXT_OBEY"] is False
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 2
        assert spider.custom_settings["DEFAULT_REQUEST_HEADERS"]["Accept"] == "application/json"

    def test_parse_normal(self, spider, markets_fixture):
        """parse should extract all fields correctly for normal entries."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=json.dumps(markets_fixture).encode())

        items = list(spider.parse(response))
        # Should have 2 entries from fixture
        assert len(items) == 2

        # Check first entry (Bitcoin)
        item1 = items[0]
        assert item1["title"] == "Bitcoin"
        assert item1["symbol"] == "btc"
        assert item1["price_usd"] == 43250.75
        assert item1["market_cap"] == 845000000000
        assert item1["volume_24h"] == 28500000000
        assert item1["rank"] == 1
        assert item1["image"] == "https://assets.coingecko.com/coins/images/1/small/bitcoin.png"
        assert item1["change_24h"] == 2.34

        # Check second entry (Ethereum)
        item2 = items[1]
        assert item2["title"] == "Ethereum"
        assert item2["symbol"] == "eth"
        assert item2["price_usd"] == 2280.50

    def test_parse_url_format(self, spider, markets_fixture):
        """url field should be formatted as 'https://www.coingecko.com/en/coins/{id}'."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=json.dumps(markets_fixture).encode())

        items = list(spider.parse(response))
        assert len(items) == 2

        # Bitcoin URL
        assert items[0]["url"] == "https://www.coingecko.com/en/coins/bitcoin"
        # Ethereum URL
        assert items[1]["url"] == "https://www.coingecko.com/en/coins/ethereum"

    def test_parse_null_change_24h(self, spider, markets_fixture):
        """price_change_percentage_24h of null should result in change_24h = None."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=json.dumps(markets_fixture).encode())

        items = list(spider.parse(response))
        # Ethereum has null price_change_percentage_24h
        ethereum_item = items[1]
        assert ethereum_item["change_24h"] is None

    def test_parse_empty_array(self, spider):
        """API returning empty array should yield 0 items."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=b"[]")

        items = list(spider.parse(response))
        assert len(items) == 0

    def test_parse_non_json_response(self, spider, caplog):
        """Non-JSON response should yield 0 items and log ERROR."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=b"This is not valid JSON")

        items = list(spider.parse(response))
        assert len(items) == 0

        # Should log an error
        assert any(record.levelname == "ERROR" for record in caplog.records)

    def test_parse_huginn_metadata(self, spider, markets_fixture):
        """Items should include Huginn metadata."""
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        response = JsonResponse(url, request=None, body=json.dumps(markets_fixture).encode())

        items = list(spider.parse(response))
        assert len(items) > 0

        item = items[0]
        assert item["_huginn_source"] == "crypto_price"
        assert item["_huginn_category"] == Category.FINANCE

    def test_start_requests_yields_one_request(self, spider):
        """start_requests should yield a single request to API URL."""
        requests = list(spider.start_requests())
        assert len(requests) == 1

        # Verify URL has correct query parameters
        expected_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        assert requests[0].url == expected_url
        assert requests[0].callback == spider.parse

    def test_api_url_constant(self, spider):
        """Spider should have correct API_URL constant."""
        assert spider.API_URL == "https://api.coingecko.com/api/v3/coins/markets"

    def test_api_params_constant(self, spider):
        """Spider should have correct API_PARAMS constant."""
        assert spider.API_PARAMS == {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
        }

    def test_coin_url_template(self, spider):
        """Spider should have correct COIN_URL_TEMPLATE constant."""
        assert spider.COIN_URL_TEMPLATE == "https://www.coingecko.com/en/coins/{id}"
