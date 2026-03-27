"""Reddit Spider.

采集 Reddit 热帖数据，使用官方 REST API（无需认证）。

API 端点: https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}
限速: 60 次/分钟
"""

import logging
from datetime import datetime, timezone

from scrapy import Request
from scrapy.http import JsonResponse, Response

from huginn.core.constants import Category
from huginn.scrapy.base_spider import BaseSpider

logger = logging.getLogger(__name__)

REDDIT_BASE_URL = "https://www.reddit.com"
SELFTEXT_MAX_LENGTH = 2000


class RedditSpider(BaseSpider):
    """Spider for collecting hot posts from Reddit subreddits.

    Reads subreddit list and limit from Scrapy settings
    (REDDIT_SUBREDDITS, REDDIT_LIMIT).

    Attributes:
        name: Spider identifier
        source_category: Data source category (COMMUNITY)
        custom_settings: Spider-level overrides (delay + User-Agent)
    """

    name = "reddit"
    source_category = Category.COMMUNITY

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "User-Agent": "huginn/1.0",
        },
    }

    # Default values used when Scrapy settings are unavailable (e.g. in tests)
    _default_subreddits = ["SideProject", "entrepreneur", "startups"]
    _default_limit = 25

    def start_requests(self):
        """Yield requests for each configured subreddit's hot feed.

        Reads REDDIT_SUBREDDITS and REDDIT_LIMIT from Scrapy settings when
        available, falling back to class-level defaults.

        Yields:
            Request: One JSON request per subreddit.
        """
        settings = getattr(self, "settings", None)
        if settings is not None:
            subreddits = settings.getlist("REDDIT_SUBREDDITS", self._default_subreddits)
            limit = settings.getint("REDDIT_LIMIT", self._default_limit)
        else:
            subreddits = self._default_subreddits
            limit = self._default_limit

        for subreddit in subreddits:
            url = f"{REDDIT_BASE_URL}/r/{subreddit}/hot.json?limit={limit}"
            yield Request(url, callback=self.parse, errback=self.handle_error)

    def parse(self, response: JsonResponse):
        """Parse the hot posts JSON response from Reddit.

        Extracts 9 fields per post: title, url, external_url, subreddit,
        score, comments, author, selftext, created_at.

        Args:
            response: JSON response from Reddit API.

        Yields:
            dict: One item per post.
        """
        data = response.json()
        children = data.get("data", {}).get("children", [])

        for child in children:
            post = child.get("data", {})

            permalink = post.get("permalink", "")
            post_url = f"{REDDIT_BASE_URL}{permalink}" if permalink else None

            raw_url = post.get("url", "")
            # external_url is the linked URL if different from the Reddit post URL
            external_url = raw_url if raw_url and not raw_url.startswith(REDDIT_BASE_URL) else None

            selftext = post.get("selftext") or None
            if selftext and len(selftext) > SELFTEXT_MAX_LENGTH:
                selftext = selftext[:SELFTEXT_MAX_LENGTH]

            created_utc = post.get("created_utc")
            if created_utc is not None:
                created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
            else:
                created_at = None

            yield self.make_item(
                title=post.get("title"),
                url=post_url,
                external_url=external_url,
                subreddit=post.get("subreddit"),
                score=int(post.get("score", 0)),
                comments=int(post.get("num_comments", 0)),
                author=post.get("author"),
                selftext=selftext,
                created_at=created_at,
            )

    def handle_error(self, failure) -> None:
        """Handle request errors, logging a warning without raising.

        Args:
            failure: Twisted Failure object from the failed request.
        """
        response: Response = failure.value.response
        logger.warning(
            "Reddit request failed: HTTP %s for %s",
            response.status,
            response.url,
        )
