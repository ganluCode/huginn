"""V2EX Spider.

采集 V2EX 热门话题，通过 V2EX API 获取：
https://www.v2ex.com/api/topics/hot.json

API 返回 JSON 数组，每个元素包含：
- id: 话题 ID
- title: 标题
- url: 链接
- content: 内容摘要
- member: 作者信息对象（包含 username 字段）
- node: 节点信息对象（包含 title 字段）
- replies: 回复数
- created: 创建时间戳
"""

from scrapy import Request
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider


class V2EXSpider(BaseSpider):
    """Spider for collecting hot topics from V2EX.

    Attributes:
        name: Spider identifier
        source_category: Data source category (TECH)
        custom_settings: Spider-specific settings override
    """

    name = "v2ex"
    source_category = Category.TECH

    # Spider-specific settings
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
        },
    }

    # V2EX API endpoint for hot topics
    HOT_TOPICS_URL = "https://www.v2ex.com/api/topics/hot.json"

    def start_requests(self):
        """Start the crawling process by fetching the hot topics.

        Yields:
            Request: A request to fetch the V2EX hot topics JSON.
        """
        yield Request(self.HOT_TOPICS_URL, callback=self.parse)

    def parse(self, response: JsonResponse):
        """Parse the hot topics JSON and yield items.

        Handles edge cases:
        - Empty JSON array: yields no items
        - Missing fields in topic objects

        Args:
            response: JSON response containing a list of hot topics.

        Yields:
            dict: Item with topic data, created via make_item().
        """
        # Parse the JSON response to get topics array
        topics = response.json()

        # Handle empty list - no topics to yield
        if not topics:
            return

        # Process each topic and yield items
        for topic in topics:
            # Extract fields with proper mapping
            # V2EX API field -> our output field
            # member.username -> author
            # node.title -> node
            title = topic.get("title")
            url = topic.get("url")
            content = topic.get("content")

            # Nested field: member.username -> author
            member = topic.get("member", {})
            author = member.get("username") if member else None

            # Nested field: node.title -> node
            node_obj = topic.get("node", {})
            node = node_obj.get("title") if node_obj else None

            replies = topic.get("replies")
            created_at = topic.get("created")

            # Build the data dict with all fields
            data = {
                "title": title,
                "url": url,
                "content": content,
                "author": author,
                "node": node,
                "replies": replies,
                "created_at": created_at,
            }

            # Use make_item to add Huginn metadata
            yield self.make_item(**data)
