"""GitHub Trending Spider.

采集 GitHub Trending 页面的热门仓库：
- URL: https://github.com/trending
- 解析 article.Box-row 元素
- 提取仓库名称、描述、语言、star 数等信息

GitHub Trending 页面结构：
- 每个趋势仓库是一个 <article class="Box-row"> 元素
- 标题链接格式: /owner/repo
- 描述在 <p class="col-9 color-fg-muted">
- 语言在 <span itemprop="programmingLanguage">
- Star 数量在包含 octicon-star 的 span 中
- Fork 数量在包含 octicon-repo-forked 的 span 中
"""

import logging

from scrapy import Spider
from scrapy.http import HtmlResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider

logger = logging.getLogger(__name__)


class GitHubTrendingSpider(BaseSpider):
    """Spider for collecting trending repositories from GitHub.

    Attributes:
        name: Spider identifier
        source_category: Data source category (TECH)
        custom_settings: Spider-specific settings
    """

    name = "github_trending"
    source_category = Category.TECH

    custom_settings = {
        "ROBOTSTXT_OBEY": False,  # GitHub robots.txt is restrictive
        "DOWNLOAD_DELAY": 1,  # Be polite to GitHub
    }

    def start_requests(self):
        """Start the crawling process by fetching GitHub trending page.

        Yields:
            Request: A request to fetch the trending page.
        """
        url = "https://github.com/trending"
        yield self.make_request(url, callback=self.parse)

    def make_request(self, url, callback):
        """Create a Scrapy request (helper method).

        Args:
            url: The URL to request.
            callback: The callback function for the response.

        Returns:
            scrapy.Request: A Scrapy Request object.
        """
        from scrapy import Request
        return Request(url, callback=callback)

    def parse(self, response: HtmlResponse):
        """Parse the trending page and extract repository data.

        Handles edge cases:
        - Missing language field (some repos don't specify language)
        - Missing description field (some repos don't have description)
        - No matching selectors (logs WARNING, yields 0 items)

        Args:
            response: HTML response from GitHub trending page.

        Yields:
            dict: Item with repository data, created via make_item().
        """
        # Select all repository entries
        articles = response.css("article.Box-row")

        # If no articles found, log warning and return
        if not articles:
            logger.warning("No trending repositories found (article.Box-row selector returned empty)")
            return

        # Parse each article
        for article in articles:
            # Extract title and URL from the main link
            # Format: /owner/repo
            href = article.css("h2.h3.lh-condensed a::attr(href)").get()
            if href:
                title = href.lstrip("/")  # Remove leading slash
                url = f"https://github.com{href}"
            else:
                # Skip if no title found (shouldn't happen normally)
                continue

            # Extract description (may not exist)
            description = article.css("p.col-9.color-fg-muted.my-1.pr-4::text").get()
            if description:
                description = description.strip()

            # Extract language (may not exist)
            language = article.css("span[itemprop=programmingLanguage]::text").get()

            # Extract stars total (raw string)
            # First star span: contains svg.octicon-star, get text from child span
            # Use XPath since Scrapy CSS doesn't support :has()
            stars_total = article.xpath(
                './/span[contains(@class, "d-inline-block") and contains(@class, "mr-3")]'
                '[.//svg[contains(@class, "octicon-star")]]'
                '[not(.//span[contains(@class, "float-sm-right")])]'
                '//span[not(@*)]/text()'
            ).get()
            if stars_total:
                stars_total = stars_total.strip()

            # Extract stars today (raw string with text)
            # Span with class "float-sm-right" that contains the "stars today" text
            stars_today = article.css(
                "span.d-inline-block.float-sm-right::text"
            ).get()
            if stars_today:
                stars_today = stars_today.strip()

            # Extract forks (raw string)
            # Span with svg.octicon-repo-forked
            forks = article.xpath(
                './/span[contains(@class, "d-inline-block") and contains(@class, "mr-3")]'
                '[.//svg[contains(@class, "octicon-repo-forked")]]'
                '//span[not(@*)]/text()'
            ).get()
            if forks:
                forks = forks.strip()

            # Build the data dict with all fields
            data = {
                "title": title,
                "url": url,
                "description": description,  # Can be None
                "language": language,  # Can be None
                "stars_total": stars_total,  # Raw string
                "stars_today": stars_today,  # Raw string with "stars today" text
                "forks": forks,  # Raw string
            }

            # Use make_item to add Huginn metadata
            yield self.make_item(**data)
