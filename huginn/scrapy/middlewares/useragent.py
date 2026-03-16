"""Random User-Agent middleware for Scrapy.

This middleware provides random User-Agent rotation for Scrapy spiders.
It helps avoid detection by rotating through a list of desktop browser User-Agents.
"""

import logging
import random
from typing import ClassVar

from scrapy import signals
from scrapy.http import Request
from scrapy.spiders import Spider
from twisted.internet.error import TimeoutError as TwistedTimeoutError

logger = logging.getLogger(__name__)


# Default list of desktop browser User-Agents (2024-2026 versions)
# Includes Chrome, Firefox, Safari, and Edge on Windows, macOS, and Linux
DEFAULT_USER_AGENTS = [
    # Chrome on Windows (2024-2026)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Chrome on macOS (2024-2026)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome on Linux (2024-2026)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows (2024-2026)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    # Firefox on macOS (2024-2026)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on Linux (2024-2026)
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Edge on Windows (2024-2026)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.112",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.2849.103",
    # Edge on macOS (2024-2026)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.112",
    # Safari on macOS (2024-2026)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    # Firefox ESR on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox ESR on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


class RandomUserAgentMiddleware:
    """Scrapy downloader middleware that sets a random User-Agent for each request.

    This middleware helps avoid detection by rotating through a list of desktop
    browser User-Agents. It respects existing User-Agent headers and can be
    configured through Scrapy settings.

    Settings:
        RANDOM_UA_ENABLED: Enable/disable the middleware (default: True)
        RANDOM_UA_LIST: Custom list of User-Agents to use (optional)

    Example:
        # In settings.py
        DOWNLOADER_MIDDLEWARES = {
            "huginn.scrapy.middlewares.useragent.RandomUserAgentMiddleware": 400,
        }
        RANDOM_UA_ENABLED = True
        RANDOM_UA_LIST = ["MyBot/1.0", "AnotherBot/2.0"]  # Optional
    """

    def __init__(self, random_ua_enabled: bool = True, random_ua_list: list[str] | None = None):
        """Initialize the middleware.

        Args:
            random_ua_enabled: Whether to enable random User-Agent rotation.
            random_ua_list: Custom list of User-Agents to use. If None, uses DEFAULT_USER_AGENTS.
        """
        self.random_ua_enabled: bool = random_ua_enabled
        self.random_ua_list: list[str] | None = random_ua_list

    @classmethod
    def from_crawler(cls, crawler) -> "RandomUserAgentMiddleware":
        """Create middleware instance from Scrapy crawler.

        This is the standard Scrapy middleware initialization method.
        It reads settings from the crawler's settings object.

        Args:
            crawler: Scrapy crawler instance with settings

        Returns:
            Configured middleware instance
        """
        settings = crawler.settings
        random_ua_enabled = settings.getbool("RANDOM_UA_ENABLED", True)
        random_ua_list = settings.getlist("RANDOM_UA_LIST", None)

        middleware = cls(
            random_ua_enabled=random_ua_enabled,
            random_ua_list=random_ua_list,
        )

        crawler.signals.connect(
            middleware.spider_opened,
            signal=signals.spider_opened,
        )

        return middleware

    def process_request(self, request: Request, spider: Spider) -> None:
        """Set a random User-Agent for the request.

        This method is called by Scrapy for each request. It:
        1. Checks if the middleware is enabled
        2. Checks if the request already has a User-Agent
        3. Sets a random User-Agent if needed

        Args:
            request: The Scrapy request being processed
            spider: The spider that generated this request

        Returns:
            None to allow normal request processing
        """
        # If disabled, do nothing
        if not self.random_ua_enabled:
            return None

        # If request already has User-Agent, don't overwrite it
        if "User-Agent" in request.headers:
            existing_ua = request.headers.get("User-Agent")
            ua_str = existing_ua.decode("utf-8") if isinstance(existing_ua, bytes) else existing_ua
            logger.debug(
                "Request already has User-Agent: %s, not overwriting",
                ua_str,
            )
            return None

        # Get the list of User-Agents to use
        ua_list = self.random_ua_list if self.random_ua_list is not None else DEFAULT_USER_AGENTS

        # Select and set a random User-Agent
        random_ua = random.choice(ua_list)
        request.headers["User-Agent"] = random_ua

        logger.debug(
            "Set random User-Agent for %s: %s",
            request.url,
            random_ua,
        )

        return None

    def spider_opened(self, spider: Spider) -> None:
        """Log when spider is opened.

        Args:
            spider: The spider that was opened
        """
        logger.info(
            "Spider opened: %s (RandomUserAgentMiddleware %s)",
            spider.name,
            "enabled" if self.random_ua_enabled else "disabled",
        )
