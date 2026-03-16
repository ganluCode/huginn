"""Proxy middleware for Scrapy.

This middleware provides proxy rotation for Scrapy spiders.
It supports static proxy lists and dynamic proxy fetching from an API.
"""

import logging
import random
import time
from typing import ClassVar

import requests
from scrapy import signals
from scrapy.http import Request
from scrapy.spiders import Spider

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """Scrapy downloader middleware that assigns proxies to requests.

    This middleware helps avoid detection and IP blocking by rotating through
    a list of proxies or dynamically fetching proxies from an API.

    Settings:
        PROXY_ENABLED: Enable/disable the middleware (default: False)
        PROXY_LIST: List of proxy URLs (e.g., ["http://proxy1:8080", ...])
        PROXY_API_URL: API endpoint to fetch proxies from (optional)
        PROXY_API_CACHE_TTL: Cache time for API proxies in seconds (default: 300)

    Example:
        # In settings.py
        DOWNLOADER_MIDDLEWARES = {
            "huginn.scrapy.middlewares.proxy.ProxyMiddleware": 350,
        }
        PROXY_ENABLED = True
        PROXY_LIST = ["http://proxy1:8080", "http://proxy2:8080"]
        # OR use API mode
        PROXY_API_URL = "http://proxy-api.com/get"
        PROXY_API_CACHE_TTL = 300
    """

    def __init__(
        self,
        proxy_enabled: bool = False,
        proxy_list: list[str] | None = None,
        proxy_api_url: str | None = None,
        proxy_api_cache_ttl: int = 300,
    ):
        """Initialize the middleware.

        Args:
            proxy_enabled: Whether to enable proxy rotation.
            proxy_list: Static list of proxy URLs. If None, defaults to empty list.
            proxy_api_url: API endpoint to fetch proxies from.
            proxy_api_cache_ttl: Cache time for API proxies in seconds.
        """
        self.proxy_enabled: bool = proxy_enabled
        self.proxy_list: list[str] = proxy_list if proxy_list is not None else []
        self.proxy_api_url: str | None = proxy_api_url
        self.proxy_api_cache_ttl: int = proxy_api_cache_ttl

        # API caching
        self._api_proxy: str | None = None
        self._api_proxy_fetched_at: float | None = None

    @classmethod
    def from_crawler(cls, crawler) -> "ProxyMiddleware":
        """Create middleware instance from Scrapy crawler.

        This is the standard Scrapy middleware initialization method.
        It reads settings from the crawler's settings object.

        Args:
            crawler: Scrapy crawler instance with settings

        Returns:
            Configured middleware instance
        """
        settings = crawler.settings
        proxy_enabled = settings.getbool("PROXY_ENABLED", False)
        proxy_list = settings.getlist("PROXY_LIST", None) or []
        proxy_api_url = settings.get("PROXY_API_URL", None)
        proxy_api_cache_ttl = settings.getint("PROXY_API_CACHE_TTL", 300)

        middleware = cls(
            proxy_enabled=proxy_enabled,
            proxy_list=proxy_list,
            proxy_api_url=proxy_api_url,
            proxy_api_cache_ttl=proxy_api_cache_ttl,
        )

        crawler.signals.connect(
            middleware.spider_opened,
            signal=signals.spider_opened,
        )

        return middleware

    def process_request(self, request: Request, spider: Spider) -> None:
        """Assign a proxy to the request.

        This method is called by Scrapy for each request. It:
        1. Checks if the middleware is enabled
        2. Checks if the request already has a proxy
        3. Assigns a proxy from the list or API if needed

        Args:
            request: The Scrapy request being processed
            spider: The spider that generated this request

        Returns:
            None to allow normal request processing
        """
        # If disabled, do nothing
        if not self.proxy_enabled:
            return None

        # If request already has proxy meta, don't overwrite it
        if "proxy" in request.meta:
            existing_proxy = request.meta.get("proxy")
            logger.debug(
                "Request already has proxy: %s, not overwriting",
                existing_proxy,
            )
            return None

        # Try to get a proxy
        proxy = self._get_proxy()

        if proxy:
            request.meta["proxy"] = proxy
            logger.debug(
                "Assigned proxy %s to %s",
                proxy,
                request.url,
            )
        else:
            logger.warning(
                "No proxy available for %s (PROXY_LIST empty and no API configured)",
                request.url,
            )

        return None

    def _get_proxy(self) -> str | None:
        """Get a proxy URL from available sources.

        Tries to get a proxy in this order:
        1. Random proxy from PROXY_LIST (if non-empty)
        2. Cached API proxy (if available and not expired)
        3. Fresh API proxy (if PROXY_API_URL is configured)

        Returns:
            Proxy URL string or None if no proxy is available
        """
        # Try static list first
        if self.proxy_list:
            return random.choice(self.proxy_list)

        # Try API mode
        if self.proxy_api_url:
            return self._fetch_proxy_from_api()

        # No proxy available
        return None

    def _fetch_proxy_from_api(self) -> str | None:
        """Fetch a proxy from the configured API URL.

        Uses caching to avoid excessive API calls. Proxies are cached
        for PROXY_API_CACHE_TTL seconds.

        Returns:
            Proxy URL string or None if API fetch fails

        Raises:
            requests.RequestException: If the API request fails
        """
        current_time = time.time()

        # Check if we have a cached proxy that's still valid
        if self._api_proxy is not None and self._api_proxy_fetched_at is not None:
            cache_age = current_time - self._api_proxy_fetched_at
            if cache_age < self.proxy_api_cache_ttl:
                logger.debug(
                    "Using cached API proxy (age: %.1fs, TTL: %ds)",
                    cache_age,
                    self.proxy_api_cache_ttl,
                )
                return self._api_proxy

        # Need to fetch a new proxy from API
        try:
            logger.debug("Fetching proxy from API: %s", self.proxy_api_url)
            response = requests.get(self.proxy_api_url, timeout=10)
            response.raise_for_status()

            # Try to get proxy from JSON response
            # Common formats: {"proxy": "http://..."}, {"data": {"proxy": "..."}}, or plain text
            try:
                data = response.json()
                proxy = data.get("proxy") or data.get("data", {}).get("proxy")
            except ValueError:
                # Not JSON, try using response text directly
                proxy = response.text.strip()

            if proxy:
                self._api_proxy = proxy
                self._api_proxy_fetched_at = current_time
                logger.info("Fetched new proxy from API: %s", proxy)
                return proxy
            else:
                logger.warning("API returned empty proxy response")
                return None

        except requests.RequestException as e:
            logger.error("Failed to fetch proxy from API: %s", e)
            # Return cached proxy if available (better than nothing)
            if self._api_proxy is not None:
                logger.warning("Using expired cached proxy due to API failure")
                return self._api_proxy
            return None

    def spider_opened(self, spider: Spider) -> None:
        """Log when spider is opened.

        Args:
            spider: The spider that was opened
        """
        logger.info(
            "Spider opened: %s (ProxyMiddleware %s)",
            spider.name,
            "enabled" if self.proxy_enabled else "disabled",
        )
        if self.proxy_enabled:
            if self.proxy_list:
                logger.info(
                    "Proxy middleware using static list (%d proxies)",
                    len(self.proxy_list),
                )
            elif self.proxy_api_url:
                logger.info(
                    "Proxy middleware using API mode: %s (cache TTL: %ds)",
                    self.proxy_api_url,
                    self.proxy_api_cache_ttl,
                )
            else:
                logger.warning(
                    "Proxy middleware enabled but no proxies configured (PROXY_LIST empty and no PROXY_API_URL)"
                )
