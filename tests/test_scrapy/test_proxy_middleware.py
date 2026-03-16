"""Test ProxyMiddleware implementation (F-002)."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from scrapy.http import Request

from huginn.scrapy.middlewares.proxy import ProxyMiddleware


class TestProxyMiddleware:
    """Verify ProxyMiddleware provides the expected interface."""

    def test_middleware_class_exists(self):
        """ProxyMiddleware class should exist."""
        assert ProxyMiddleware is not None

    def test_from_crawler_creates_middleware(self):
        """from_crawler should create a configured middleware instance."""
        mock_crawler = MagicMock()
        mock_settings = MagicMock()
        mock_settings.getbool = MagicMock(return_value=True)
        mock_settings.getlist = MagicMock(return_value=["http://proxy1:8080"])
        mock_settings.get = MagicMock(return_value="http://proxy-api.com")
        mock_settings.getint = MagicMock(return_value=300)
        mock_crawler.settings = mock_settings

        middleware = ProxyMiddleware.from_crawler(mock_crawler)

        assert middleware.proxy_enabled is True
        assert middleware.proxy_list == ["http://proxy1:8080"]
        assert middleware.proxy_api_url == "http://proxy-api.com"
        assert middleware.proxy_api_cache_ttl == 300

    def test_from_crawler_default_settings(self):
        """from_crawler should use default settings when not configured."""
        mock_crawler = MagicMock()
        mock_settings = MagicMock()
        mock_settings.getbool = MagicMock(return_value=False)
        mock_settings.getlist = MagicMock(return_value=None)
        mock_settings.get = MagicMock(return_value=None)
        mock_settings.getint = MagicMock(return_value=300)
        mock_crawler.settings = mock_settings

        middleware = ProxyMiddleware.from_crawler(mock_crawler)

        assert middleware.proxy_enabled is False
        assert middleware.proxy_list == []
        assert middleware.proxy_api_url is None
        assert middleware.proxy_api_cache_ttl == 300

    def test_process_request_when_disabled(self, caplog):
        """When PROXY_ENABLED=False, process_request should not set proxy."""
        middleware = ProxyMiddleware(proxy_enabled=False)
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # proxy meta should not be set
        assert "proxy" not in request.meta

    def test_process_request_skips_existing_proxy(self, caplog):
        """When request already has proxy meta, it should not be overwritten."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://proxy1:8080", "http://proxy2:8080"]
        )
        existing_proxy = "http://existing-proxy:9090"
        request = Request("http://example.com")
        request.meta["proxy"] = existing_proxy

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # proxy should remain unchanged
        assert request.meta["proxy"] == existing_proxy

    def test_process_request_assigns_random_proxy_from_list(self, caplog):
        """When PROXY_LIST is non-empty, should assign random proxy."""
        proxy_list = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=proxy_list
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # proxy should be set from the list
        assert "proxy" in request.meta
        assert request.meta["proxy"] in proxy_list

    def test_process_request_warns_when_no_proxy_available(self, caplog):
        """When PROXY_LIST is empty and no API URL, should log WARNING."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[],
            proxy_api_url=None
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.WARNING):
            result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # proxy should not be set
        assert "proxy" not in request.meta
        # Should log a WARNING
        assert any("proxy" in record.message.lower() for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_process_request_uses_proxy_api_when_configured(self, caplog):
        """When PROXY_API_URL is set, should call API to get proxy."""
        api_proxy = "http://api-proxy:9999"

        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[],
            proxy_api_url="http://proxy-api.com/get",
            proxy_api_cache_ttl=300
        )
        request = Request("http://example.com")

        # Mock the _fetch_proxy_from_api method
        with patch.object(middleware, "_fetch_proxy_from_api", return_value=api_proxy):
            with caplog.at_level(logging.DEBUG):
                result = middleware.process_request(request, None)

        # process_request should return None
        assert result is None
        # proxy should be set from API
        assert request.meta["proxy"] == api_proxy

    def test_fetch_proxy_from_api_caches_result(self):
        """_fetch_proxy_from_api should cache the result for TTL seconds."""
        import time

        api_proxy = "http://api-proxy:9999"

        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_api_url="http://proxy-api.com/get",
            proxy_api_cache_ttl=1  # 1 second TTL
        )

        # Mock requests.get
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"proxy": api_proxy}
            mock_get.return_value.status_code = 200
            mock_get.return_value.raise_for_status = MagicMock()

            # First call should hit the API
            result1 = middleware._fetch_proxy_from_api()
            assert result1 == api_proxy
            assert mock_get.call_count == 1

            # Immediate second call should use cache
            result2 = middleware._fetch_proxy_from_api()
            assert result2 == api_proxy
            assert mock_get.call_count == 1  # Not incremented

            # Wait for cache to expire
            time.sleep(1.1)

            # Third call should hit the API again
            result3 = middleware._fetch_proxy_from_api()
            assert result3 == api_proxy
            assert mock_get.call_count == 2

    def test_logs_debug_message_when_assigning_proxy(self, caplog):
        """process_request should log DEBUG message when assigning proxy."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://proxy1:8080"]
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            middleware.process_request(request, None)

        # Should have a DEBUG log about proxy assignment
        assert any("proxy" in record.message.lower() for record in caplog.records)

    def test_multiple_requests_get_random_proxies(self):
        """Multiple requests should get (potentially) different proxies."""
        proxy_list = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=proxy_list
        )

        requests = [Request(f"http://example{i}.com") for i in range(10)]

        for req in requests:
            middleware.process_request(req, None)

        # Collect all assigned proxies
        proxies = [req.meta.get("proxy") for req in requests]

        # All should have a proxy assigned
        assert all(p is not None for p in proxies)

        # With 3 proxies and 10 requests, we should get some variety
        # (Not guaranteed, but highly likely)
        assert len(set(proxies)) >= 2

    def test_proxy_format_http(self, caplog):
        """Proxy in http://host:port format should work correctly."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://proxy.example.com:8080"]
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        assert result is None
        assert request.meta["proxy"] == "http://proxy.example.com:8080"

    def test_proxy_format_https(self, caplog):
        """Proxy in https://host:port format should work correctly."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["https://proxy.example.com:8443"]
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        assert result is None
        assert request.meta["proxy"] == "https://proxy.example.com:8443"

    def test_proxy_format_with_auth(self, caplog):
        """Proxy with authentication (http://user:pass@host:port) should work."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://user:pass@proxy.example.com:8080"]
        )
        request = Request("http://example.com")

        with caplog.at_level(logging.DEBUG):
            result = middleware.process_request(request, None)

        assert result is None
        assert request.meta["proxy"] == "http://user:pass@proxy.example.com:8080"

    def test_empty_proxy_list_with_api_url_calls_api(self, caplog):
        """When proxy list is empty but API URL is set, should call API."""
        api_proxy = "http://api-proxy:9999"

        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[],
            proxy_api_url="http://proxy-api.com/get"
        )
        request = Request("http://example.com")

        with patch.object(middleware, "_fetch_proxy_from_api", return_value=api_proxy):
            with caplog.at_level(logging.DEBUG):
                result = middleware.process_request(request, None)

        assert result is None
        assert request.meta["proxy"] == api_proxy

    def test_api_returns_none_falls_back_to_direct(self, caplog):
        """When API returns None/empty, should fall back to direct connection."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[],
            proxy_api_url="http://proxy-api.com/get"
        )
        request = Request("http://example.com")

        with patch.object(middleware, "_fetch_proxy_from_api", return_value=None):
            with caplog.at_level(logging.WARNING):
                result = middleware.process_request(request, None)

        assert result is None
        assert "proxy" not in request.meta
