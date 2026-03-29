"""Google Trends Spider.

采集 Google 热搜榜数据，使用 pytrends 库。

pytrends 为非官方接口，可能不稳定，单个地区最多重试 3 次（间隔 60 秒）。
"""

import logging
import time
import urllib.parse

import requests
import scrapy
from pytrends.exceptions import TooManyRequestsError
from pytrends.request import TrendReq

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_BASE = "https://www.google.com/search"
GOOGLE_TRENDS_REGIONS = ["china", "united_states"]
_MAX_RETRIES = 3
_RETRY_DELAY = 60  # seconds between retries


class GoogleTrendsSpider(BaseSpider):
    """Spider for collecting Google trending searches via pytrends.

    Uses pytrends.TrendReq to fetch daily trending searches for each
    configured region. Each trending term is yielded as an item with
    title, url (Google search link), region, and rank fields.

    Attributes:
        name: Spider identifier
        source_category: Data source category (TRENDS)
    """

    name = "google_trends"
    source_category = Category.TRENDS

    _default_regions = GOOGLE_TRENDS_REGIONS

    def start_requests(self):
        """Yield one Scrapy Request per region to drive per-region collection.

        Instantiates TrendReq once for the full crawl and stores it as
        self._pytrends. Each request carries the region in meta so that
        parse() can retrieve it without re-instantiating pytrends.

        Reads GOOGLE_TRENDS_REGIONS from Scrapy settings when available,
        falling back to class-level defaults.

        Yields:
            scrapy.Request: One request per region with meta["region"] set.
        """
        self._pytrends = TrendReq(hl="zh-CN", tz=480)

        settings = getattr(self, "settings", None)
        regions = (
            settings.getlist("GOOGLE_TRENDS_REGIONS", self._default_regions)
            if settings
            else list(self._default_regions)
        )

        for region in regions:
            yield scrapy.Request(
                url=f"https://trends.google.com/trends/trendingsearches/daily?geo={region}",
                meta={"region": region},
                callback=self.parse,
                dont_filter=True,
            )

    def parse(self, response):
        """Fetch trending searches for the region and yield items.

        Ignores the HTTP response body; uses response.meta["region"] to
        call pytrends.trending_searches(pn=region) and yield one item per
        trending term.

        Args:
            response: Scrapy response (body ignored; region read from meta).

        Yields:
            dict: Item with title, url, region, rank fields plus Huginn metadata.
        """
        region = response.meta["region"]
        yield from self._collect_region(region)

    def _collect_region(self, region):
        """Collect trending searches for a single region with retry logic.

        Retries up to _MAX_RETRIES times on Timeout or 429 errors, sleeping
        _RETRY_DELAY seconds between attempts. After all retries are exhausted,
        logs an error and returns without raising.

        Args:
            region: pytrends region identifier (e.g. 'china', 'united_states').

        Yields:
            dict: Item per trending term.
        """
        for attempt in range(_MAX_RETRIES + 1):
            try:
                df = self._pytrends.trending_searches(pn=region)
                if df.empty:
                    logger.warning("Empty trending searches for region: %s", region)
                    return
                for rank, title in enumerate(df[0], start=1):
                    title_str = str(title)
                    search_url = f"{GOOGLE_SEARCH_BASE}?q={urllib.parse.quote(title_str)}"
                    yield self.make_item(
                        title=title_str,
                        url=search_url,
                        region=region,
                        rank=rank,
                    )
                return
            except requests.exceptions.Timeout as exc:
                logger.error(
                    "Timeout fetching trends for %s (attempt %d/%d): %s",
                    region,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                )
            except TooManyRequestsError as exc:
                logger.error(
                    "429 Too Many Requests for %s (attempt %d/%d): %s",
                    region,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                )

            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)
