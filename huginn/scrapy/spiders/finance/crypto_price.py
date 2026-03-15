"""CoinGecko Spider.

采集 CoinGecko 市场数据：
- URL: https://api.coingecko.com/api/v3/coins/markets
- 参数: vs_currency=usd, order=market_cap_desc, per_page=50, page=1
- 解析 JSON 响应，提取加密货币价格、市值、交易量等数据

CoinGecko Markets API:
- 返回格式: JSON 数组，每条记录包含一个币种的数据
- 字段: id, name, symbol, current_price, market_cap, total_volume,
        market_cap_rank, image, price_change_percentage_24h (可能为 null)
"""

import logging

from scrapy import Request
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider

logger = logging.getLogger(__name__)


class CoinGeckoSpider(BaseSpider):
    """Spider for collecting cryptocurrency market data from CoinGecko.

    Attributes:
        name: Spider identifier
        source_category: Data source category (FINANCE)
        custom_settings: Spider-specific settings
    """

    name = "crypto_price"
    source_category = Category.FINANCE

    custom_settings = {
        "ROBOTSTXT_OBEY": False,  # API endpoint, no robots.txt needed
        "DOWNLOAD_DELAY": 2,  # Be polite to CoinGecko API
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
        },
    }

    # CoinGecko API endpoint
    API_URL = "https://api.coingecko.com/api/v3/coins/markets"

    # API parameters
    API_PARAMS = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
    }

    # CoinGecko website URL template for each coin
    COIN_URL_TEMPLATE = "https://www.coingecko.com/en/coins/{id}"

    def start_requests(self):
        """Start the crawling process by fetching the markets data.

        Yields:
            Request: A request to fetch the markets JSON.
        """
        # Build URL with query parameters
        from urllib.parse import urlencode

        url = f"{self.API_URL}?{urlencode(self.API_PARAMS)}"
        yield Request(url, callback=self.parse)

    def parse(self, response: JsonResponse):
        """Parse the markets JSON and extract cryptocurrency data.

        Handles edge cases:
        - Non-JSON response (logs ERROR, yields 0 items)
        - Empty array response (API returned no data)
        - Null price_change_percentage_24h field (change_24h = None)

        Args:
            response: JSON response containing market data array.

        Yields:
            dict: Item with cryptocurrency data, created via make_item().
        """
        try:
            # Parse the JSON response
            coins = response.json()
        except Exception as e:
            # Response cannot be parsed as JSON
            logger.error("Failed to parse CoinGecko API response as JSON: %s", e)
            return

        # Check if response is empty array
        if not coins:
            # API returned empty array - no data
            return

        # Parse each coin record
        for coin in coins:
            # Extract fields with proper mapping
            # API field -> our output field
            # name -> title, current_price -> price_usd, etc.
            coin_id = coin.get("id")
            title = coin.get("name")
            symbol = coin.get("symbol")
            price_usd = coin.get("current_price")
            market_cap = coin.get("market_cap")
            volume_24h = coin.get("total_volume")
            rank = coin.get("market_cap_rank")
            image = coin.get("image")
            change_24h = coin.get("price_change_percentage_24h")  # May be None

            # Build URL to CoinGecko website for this coin
            url = self.COIN_URL_TEMPLATE.format(id=coin_id) if coin_id else None

            # Build the data dict with all fields
            data = {
                "title": title,
                "symbol": symbol,
                "price_usd": price_usd,
                "change_24h": change_24h,  # None if field is null in API
                "market_cap": market_cap,
                "volume_24h": volume_24h,
                "rank": rank,
                "image": image,
                "url": url,
            }

            # Use make_item to add Huginn metadata
            yield self.make_item(**data)
