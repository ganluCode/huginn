"""App Store Spider.

采集 Apple App Store 免费榜/付费榜/畅销榜数据。

API 端点: https://rss.applemarketingtools.com/api/v2/{country}/apps/{chart}/{limit}/apps.json
无需认证，Apple 官方 RSS Feed。
"""

import logging

from scrapy import Request
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider

logger = logging.getLogger(__name__)

APPSTORE_BASE_URL = "https://rss.applemarketingtools.com/api/v2"

_DEFAULT_TARGETS = [
    {"country": "cn", "chart": "top-free", "limit": 25},
    {"country": "cn", "chart": "top-grossing", "limit": 25},
    {"country": "us", "chart": "top-free", "limit": 25},
]


class AppstoreSpider(BaseSpider):
    """Spider for collecting App Store chart rankings.

    Reads chart targets from Scrapy settings (APPSTORE_TARGETS).
    Each target specifies country, chart type, and number of apps.

    Attributes:
        name: Spider identifier
        source_category: Data source category (MARKET)
    """

    name = "appstore"
    source_category = Category.MARKET

    def start_requests(self):
        """Yield requests for each configured App Store chart target.

        Reads APPSTORE_TARGETS from Scrapy settings when available,
        falling back to built-in defaults.

        Yields:
            Request: One JSON request per chart target.
        """
        settings = getattr(self, "settings", None)
        if settings is not None:
            targets = settings.getlist("APPSTORE_TARGETS", _DEFAULT_TARGETS)
        else:
            targets = _DEFAULT_TARGETS

        for target in targets:
            country = target["country"]
            chart = target["chart"]
            limit = target["limit"]
            url = f"{APPSTORE_BASE_URL}/{country}/apps/{chart}/{limit}/apps.json"
            yield Request(
                url,
                callback=self.parse,
                cb_kwargs={"chart": chart, "country": country},
            )

    def parse(self, response: JsonResponse, chart: str, country: str):
        """Parse the App Store RSS Feed JSON response.

        Extracts 10 fields per app: title, url, artist, category, chart,
        country, rank, app_id, artwork_url, release_date.

        Args:
            response: JSON response from Apple RSS Feed API.
            chart: Chart type (e.g. 'top-free', 'top-grossing').
            country: Country code (e.g. 'cn', 'us').

        Yields:
            dict: One item per app in the chart.
        """
        data = response.json()
        results = data.get("feed", {}).get("results", [])

        if not results:
            logger.warning(
                "No results found for chart=%s country=%s url=%s",
                chart,
                country,
                response.url,
            )
            return

        for rank, app in enumerate(results, start=1):
            genres = app.get("genres", [])
            category = genres[0]["name"] if genres else None

            yield self.make_item(
                title=app.get("name"),
                url=app.get("url"),
                artist=app.get("artistName"),
                category=category,
                chart=chart,
                country=country,
                rank=rank,
                app_id=app.get("id"),
                artwork_url=app.get("artworkUrl100"),
                release_date=app.get("releaseDate"),
            )
