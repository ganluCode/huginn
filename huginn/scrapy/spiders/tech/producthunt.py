"""ProductHunt Spider.

采集 ProductHunt 首页热门产品列表：
https://www.producthunt.com/

ProductHunt 首页展示今日热门产品，每个产品卡片包含：
- title: 产品名称
- url: 产品链接（相对路径）
- tagline: 产品标语
- votes: 投票数
- topics: 相关主题标签（多个）
"""

from scrapy import Request
from scrapy.http import HtmlResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider


class ProductHuntSpider(BaseSpider):
    """Spider for collecting top products from ProductHunt.

    Attributes:
        name: Spider identifier
        source_category: Data source category (TECH)
    """

    name = "producthunt"
    source_category = Category.TECH

    # ProductHunt homepage URL
    HOMEPAGE_URL = "https://www.producthunt.com/"

    def start_requests(self):
        """Start the crawling process by fetching the homepage.

        Yields:
            Request: A request to fetch the ProductHunt homepage HTML.
        """
        yield Request(self.HOMEPAGE_URL, callback=self.parse)

    def parse(self, response: HtmlResponse):
        """Parse the homepage HTML and yield product items.

        Handles edge cases:
        - Empty product list: yields no items
        - Missing fields (tagline, votes, topics): sets them to None

        Args:
            response: HTML response containing product listings.

        Yields:
            dict: Item with product data, created via make_item().
        """
        # Select all product cards
        # ProductHunt uses specific CSS classes for product cards
        products = response.css('article.styles_tileWrapper__PFwr_')

        # Handle empty list - no products to yield
        if not products:
            return

        # Process each product and yield items
        for product in products:
            # Extract title from the link text
            title_elem = product.css('header h2 a::text')
            title = title_elem.get() if title_elem else None

            # Extract URL from the link href
            url_elem = product.css('header h2 a::attr(href)')
            url = url_elem.get() if url_elem else None

            # Extract tagline (may be missing)
            tagline_elem = product.css('div.styles_tagline__fJdXv::text')
            tagline = tagline_elem.get().strip() if tagline_elem else None

            # Extract votes (may be missing)
            votes_elem = product.css('div.styles_voteButton__T2NJ3 button::text')
            votes = votes_elem.get().strip() if votes_elem else None

            # Extract topics (may be missing, multiple topics)
            topics_elems = product.css('div.styles_topics__K_nVP a::text')
            topics = [t.strip() for t in topics_elems.getall()] if topics_elems else None

            # Build the data dict with all fields
            data = {
                "title": title,
                "url": url,
                "tagline": tagline,
                "votes": votes,
                "topics": topics,
            }

            # Use make_item to add Huginn metadata
            yield self.make_item(**data)
