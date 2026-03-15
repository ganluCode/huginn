"""HackerNews Spider.

采集 HackerNews Top 30 故事，通过两阶段请求：
1. 获取 topstories JSON 列表
2. 逐个请求每个 story 详情

HackerNews API:
- Top stories: https://hacker-news.firebaseio.com/v0/topstories.json
- Item detail: https://hacker-news.firebaseio.com/v0/item/{id}.json
"""

from scrapy import Request
from scrapy.http import JsonResponse

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider


class HackerNewsSpider(BaseSpider):
    """Spider for collecting top stories from HackerNews.

    Attributes:
        name: Spider identifier
        source_category: Data source category (TECH)
    """

    name = "hackernews"
    source_category = Category.TECH

    # HackerNews Firebase API endpoints
    TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

    # Maximum number of stories to collect
    MAX_STORIES = 30

    def start_requests(self):
        """Start the crawling process by fetching the top stories list.

        Yields:
            Request: A request to fetch the top stories JSON.
        """
        yield Request(self.TOPSTORIES_URL, callback=self.parse)

    def parse(self, response: JsonResponse):
        """Parse the top stories JSON and yield requests for each story.

        Args:
            response: JSON response containing a list of story IDs.

        Yields:
            Request: A request for each of the first MAX_STORIES story IDs.
        """
        # Parse the JSON response to get story IDs
        story_ids = response.json()

        if not story_ids:
            # Empty list - no stories to fetch
            return

        # Limit to MAX_STORIES stories
        for story_id in story_ids[: self.MAX_STORIES]:
            item_url = self.ITEM_URL_TEMPLATE.format(id=story_id)
            yield Request(item_url, callback=self.parse_story)

    def parse_story(self, response: JsonResponse):
        """Parse an individual story and extract data.

        Handles edge cases:
        - Null story (response body is "null")
        - Missing url field (some stories are Ask HN, etc.)
        - Missing descendants field (no comments yet)

        Args:
            response: JSON response containing story details.

        Yields:
            dict: Item with story data, created via make_item().
        """
        # Parse the JSON response
        story = response.json()

        # Handle null story - could be deleted or unavailable
        if story is None:
            return

        # Extract fields with proper mapping
        # HN API field -> our output field
        # id -> hn_id, by -> author, descendants -> comments
        hn_id = story.get("id")
        title = story.get("title")
        url = story.get("url")  # May be None for Ask HN, etc.
        score = story.get("score")
        author = story.get("by")
        comments = story.get("descendants", 0)  # Default to 0 if missing

        # Build the data dict with all fields
        data = {
            "hn_id": hn_id,
            "title": title,
            "url": url,  # Can be None
            "score": score,
            "author": author,
            "comments": comments,  # 0 if descendants field is missing
        }

        # Use make_item to add Huginn metadata
        yield self.make_item(**data)
