"""Scrapy downloader middlewares for Huginn."""

from huginn.scrapy.middlewares.proxy import ProxyMiddleware
from huginn.scrapy.middlewares.useragent import RandomUserAgentMiddleware

__all__ = ["ProxyMiddleware", "RandomUserAgentMiddleware"]
