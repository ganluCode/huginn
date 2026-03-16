"""Test RandomUserAgentMiddleware implementation (F-001)."""

import logging

import pytest
from scrapy.exceptions import NotConfigured
from scrapy.http import Request
from twisted.internet.error import TimeoutError

from huginn.scrapy.middlewares.useragent import RandomUserAgentMiddleware, DEFAULT_USER_AGENTS


class TestRandomUserAgentMiddleware:
    """Verify RandomUserAgentMiddleware provides the expected interface."""

    def test_middleware_class_exists(self):
        """RandomUserAgentMiddleware class should exist."""
        assert RandomUserAgentMiddleware is not None

    def test_default_ua_list_has_at_least_20_entries(self):
        """DEFAULT_USER_AGENTS should have at least 20 entries."""
        assert len(DEFAULT_USER_AGENTS) >= 20

    def test_default_ua_list_contains_desktop_browsers(self):
        """DEFAULT_USER_AGENTS should contain Chrome/Firefox/Safari/Edge desktop UAs."""
        # Check that we have UAs from major desktop browsers
        ua_strings = " ".join(DEFAULT_USER_AGENTS)
        assert "Chrome" in ua_strings
        assert "Firefox" in ua_strings
        assert "Safari" in ua_strings or "Edg" in ua_strings

    def test_default_ua_list_contains_recent_versions(self):
        """DEFAULT_USER_AGENTS should contain recent browser versions (2024-2026)."""
        ua_strings = " ".join(DEFAULT_USER_AGENTS)
        # Check for recent version numbers
        assert any(year in ua_strings for year in ["2024", "2025", "2026", "124", "125", "126", "127", "128", "129", "130", "131", "132", "133"])

    def test_process_request_when_enabled(self, caplog):
        """When RANDOM_UA_ENABLED=True, process_request should set User-Agent."""
        middleware = RandomUserAgentMiddleware()
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # User-Agent header should be set
        assert "User-Agent" in request.headers
        ua_bytes = request.headers.get("User-Agent")
        assert ua_bytes is not None
        ua = ua_bytes.decode("utf-8") if isinstance(ua_bytes, bytes) else ua_bytes
        assert len(ua) > 0
        # Should come from DEFAULT_USER_AGENTS
        assert ua in DEFAULT_USER_AGENTS

    def test_process_request_when_disabled(self, caplog):
        """When RANDOM_UA_ENABLED=False, process_request should not modify request."""
        middleware = RandomUserAgentMiddleware()
        middleware.random_ua_enabled = False
        request = Request("http://example.com")

        original_ua = request.headers.get("User-Agent")
        result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # User-Agent should not be set/modified
        assert request.headers.get("User-Agent") == original_ua

    def test_process_request_preserves_existing_ua(self, caplog):
        """When request already has User-Agent, it should not be overwritten."""
        middleware = RandomUserAgentMiddleware()
        custom_ua = "MyCustomBot/1.0"
        request = Request("http://example.com", headers={"User-Agent": custom_ua})

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # User-Agent should remain unchanged
        ua_bytes = request.headers.get("User-Agent")
        ua = ua_bytes.decode("utf-8") if isinstance(ua_bytes, bytes) else ua_bytes
        assert ua == custom_ua

    def test_process_request_uses_custom_list_when_provided(self, caplog):
        """When RANDOM_UA_LIST is set, use it instead of DEFAULT_USER_AGENTS."""
        custom_ua_list = [
            "CustomBrowser/1.0",
            "AnotherBrowser/2.0",
            "ThirdBrowser/3.0",
        ]
        middleware = RandomUserAgentMiddleware()
        middleware.random_ua_list = custom_ua_list
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # User-Agent should be from custom list
        ua_bytes = request.headers.get("User-Agent")
        ua = ua_bytes.decode("utf-8") if isinstance(ua_bytes, bytes) else ua_bytes
        assert ua in custom_ua_list

    def test_multiple_requests_get_different_uas(self, caplog):
        """Multiple requests should (likely) get different User-Agents."""
        middleware = RandomUserAgentMiddleware()
        request1 = Request("http://example1.com")
        request2 = Request("http://example2.com")
        request3 = Request("http://example3.com")
        request4 = Request("http://example4.com")
        request5 = Request("http://example5.com")

        with caplog.at_level(logging.DEBUG):
            middleware.process_request(request1, None)
            middleware.process_request(request2, None)
            middleware.process_request(request3, None)
            middleware.process_request(request4, None)
            middleware.process_request(request5, None)

        def decode_ua(ua_bytes):
            return ua_bytes.decode("utf-8") if isinstance(ua_bytes, bytes) else ua_bytes

        ua1 = decode_ua(request1.headers.get("User-Agent"))
        ua2 = decode_ua(request2.headers.get("User-Agent"))
        ua3 = decode_ua(request3.headers.get("User-Agent"))
        ua4 = decode_ua(request4.headers.get("User-Agent"))
        ua5 = decode_ua(request5.headers.get("User-Agent"))

        # With 20+ UAs and 5 requests, we should get some variety
        # (Not guaranteed, but highly likely)
        all_uas = [ua1, ua2, ua3, ua4, ua5]
        assert len(set(all_uas)) >= 2  # At least 2 different UAs

    def test_logs_debug_message_when_setting_ua(self, caplog):
        """process_request should log a DEBUG message when setting User-Agent."""
        middleware = RandomUserAgentMiddleware()
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            middleware.process_request(request, None)

        # Should have a DEBUG log about setting User-Agent
        assert any("User-Agent" in record.message for record in caplog.records)
        assert any(record.levelno == logging.DEBUG for record in caplog.records)

    def test_from_crawler_stores_settings(self):
        """from_crawler should properly configure middleware from settings."""
        from unittest.mock import MagicMock

        # Create a mock crawler with settings
        mock_crawler = MagicMock()
        mock_settings = MagicMock()
        mock_settings.getbool = MagicMock(return_value=False)
        mock_settings.getlist = MagicMock(return_value=["CustomUA/1.0"])
        mock_crawler.settings = mock_settings

        middleware = RandomUserAgentMiddleware.from_crawler(mock_crawler)

        assert middleware.random_ua_enabled is False
        assert middleware.random_ua_list == ["CustomUA/1.0"]
