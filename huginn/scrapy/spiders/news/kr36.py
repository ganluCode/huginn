"""36kr Spider.

采集 36kr 快讯列表：
https://36kr.com/newsflashes

36kr 快讯页面展示实时科技快讯，每条快讯包含：
- title: 快讯标题
- url: 快讯详情链接
- summary: 快讯摘要内容
- published_at: 发布时间
"""

from scrapy import Request
from scrapy.http import HtmlResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider


class Kr36Spider(BaseSpider):
    """Spider for collecting news flashes from 36kr.

    Attributes:
        name: Spider identifier
        source_category: Data source category (NEWS)
        custom_settings: Spider-specific settings override
    """

    name = "kr36"
    source_category = Category.NEWS

    # Spider-specific settings
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
    }

    # 36kr news flashes URL
    NEWSFLASHES_URL = "https://36kr.com/newsflashes"

    def start_requests(self):
        """Start the crawling process by fetching the news flashes page.

        Yields:
            Request: A request to fetch the 36kr news flashes HTML.
        """
        yield Request(self.NEWSFLASHES_URL, callback=self.parse)

    def parse(self, response: HtmlResponse):
        """Parse the news flashes HTML and yield items.

        Handles edge cases:
        - Empty news flash list: yields no items
        - Missing fields (summary, published_at): sets them to None

        Args:
            response: HTML response containing news flash listings.

        Yields:
            dict: Item with news flash data, created via make_item().
        """
        # Select all news flash items
        # 36kr uses specific CSS classes for news flash items
        items = response.css('div.newsflash-item')

        # Handle empty list - no items to yield
        if not items:
            return

        # Process each news flash and yield items
        for item in items:
            # Extract title from the link text
            title_elem = item.css('a.title::text')
            title = title_elem.get() if title_elem else None

            # Extract URL from the link href
            url_elem = item.css('a.title::attr(href)')
            url = url_elem.get() if url_elem else None

            # Extract summary (may be missing)
            summary_elem = item.css('div.summary::text')
            summary = summary_elem.get().strip() if summary_elem else None

            # Extract published_at (may be missing)
            published_at_elem = item.css('time::attr(datetime)')
            published_at = published_at_elem.get() if published_at_elem else None

            # Build the data dict with all fields
            data = {
                "title": title,
                "url": url,
                "summary": summary,
                "published_at": published_at,
            }

            # Use make_item to add Huginn metadata
            yield self.make_item(**data)
