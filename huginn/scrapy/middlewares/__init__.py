"""Scrapy downloader middlewares for Huginn."""

from huginn.scrapy.middlewares.useragent import RandomUserAgentMiddleware

__all__ = ["RandomUserAgentMiddleware"]
