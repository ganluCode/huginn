"""Test ProxyMiddleware implementation (F-002, F-003)."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from scrapy.exceptions import NotConfigured
from scrapy.http import Request, Response
from twisted.internet.error import ConnectionRefusedError, ConnectError, TimeoutError

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


class TestProxyMiddlewareFailureTracking:
    """Verify ProxyMiddleware failure tracking and proxy removal (F-003)."""

    def test_from_crawler_loads_proxy_max_fail_setting(self):
        """from_crawler should load PROXY_MAX_FAIL setting (default 3)."""
        mock_crawler = MagicMock()
        mock_settings = MagicMock()
        mock_settings.getbool = MagicMock(return_value=False)
        mock_settings.getlist = MagicMock(return_value=None)
        mock_settings.get = MagicMock(return_value=None)
        mock_settings.getint = MagicMock(return_value=5)  # Custom max fail
        mock_crawler.settings = mock_settings

        middleware = ProxyMiddleware.from_crawler(mock_crawler)

        assert middleware.proxy_max_fail == 5

    def test_from_crawler_default_proxy_max_fail(self):
        """from_crawler should use default PROXY_MAX_FAIL=3 when not set."""
        mock_crawler = MagicMock()
        mock_settings = MagicMock()
        mock_settings.getbool = MagicMock(return_value=False)
        mock_settings.getlist = MagicMock(return_value=None)
        mock_settings.get = MagicMock(return_value=None)
        mock_settings.getint = MagicMock(side_effect=lambda key, default: default)
        mock_crawler.settings = mock_settings

        middleware = ProxyMiddleware.from_crawler(mock_crawler)

        assert middleware.proxy_max_fail == 3

    def test_process_exception_handles_connection_refused_error(self, caplog):
        """process_exception should handle ConnectionRefusedError by marking proxy failed."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")

        with caplog.at_level(logging.WARNING):
            result = middleware.process_exception(request, spider, exception)

        # Should return the request to trigger retry
        assert result is request
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_exception_handles_timeout_error(self, caplog):
        """process_exception should handle TimeoutError by marking proxy failed."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = TimeoutError("Connection timed out")

        with caplog.at_level(logging.WARNING):
            result = middleware.process_exception(request, spider, exception)

        # Should return the request to trigger retry
        assert result is request
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_exception_handles_connect_error_base_class(self, caplog):
        """process_exception should handle ConnectError (base class) by marking proxy failed."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        # Use a generic ConnectError (covers various connection-related errors)
        exception = ConnectError("Connection failed")

        with caplog.at_level(logging.WARNING):
            result = middleware.process_exception(request, spider, exception)

        # Should return the request to trigger retry
        assert result is request
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_exception_ignores_other_exceptions(self, caplog):
        """process_exception should ignore non-connection exceptions."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ValueError("Some other error")

        with caplog.at_level(logging.WARNING):
            result = middleware.process_exception(request, spider, exception)

        # Should return None to not handle this exception
        assert result is None
        # Proxy should NOT be marked as failed
        assert proxy not in middleware._proxy_fail_counts

    def test_process_exception_removes_proxy_after_max_failures(self, caplog):
        """process_exception should remove proxy after PROXY_MAX_FAIL failures."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")

        # Fail 3 times (max_fail = 3)
        for i in range(3):
            with caplog.at_level(logging.WARNING):
                middleware.process_exception(request, spider, exception)

        # After 3 failures, proxy should be removed from list
        assert proxy not in middleware.proxy_list
        # And should not be in fail counts
        assert proxy not in middleware._proxy_fail_counts
        # Should have logged an ERROR about removal
        assert any(
            record.levelno == logging.ERROR
            and "removed" in record.message.lower()
            for record in caplog.records
        )

    def test_process_exception_logs_warning_on_each_failure(self, caplog):
        """process_exception should log WARNING on each failure before removal."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")

        with caplog.at_level(logging.WARNING):
            middleware.process_exception(request, spider, exception)

        # Should have logged a WARNING about the failure
        assert any(
            record.levelno == logging.WARNING
            and "failed" in record.message.lower()
            for record in caplog.records
        )

    def test_process_response_handles_403_status(self, caplog):
        """process_response should mark proxy failed on 403 status."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        response = Response("http://example.com", status=403)
        spider = MagicMock()

        with caplog.at_level(logging.WARNING):
            result = middleware.process_response(request, response, spider)

        # Should return the response
        assert result is response
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_response_handles_407_status(self, caplog):
        """process_response should mark proxy failed on 407 status."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        response = Response("http://example.com", status=407)
        spider = MagicMock()

        with caplog.at_level(logging.WARNING):
            result = middleware.process_response(request, response, spider)

        # Should return the response
        assert result is response
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_response_handles_429_status(self, caplog):
        """process_response should mark proxy failed on 429 status."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        response = Response("http://example.com", status=429)
        spider = MagicMock()

        with caplog.at_level(logging.WARNING):
            result = middleware.process_response(request, response, spider)

        # Should return the response
        assert result is response
        # Proxy should be marked as failed
        assert proxy in middleware._proxy_fail_counts
        assert middleware._proxy_fail_counts[proxy] == 1

    def test_process_response_ignores_other_statuses(self, caplog):
        """process_response should ignore other HTTP status codes."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        response = Response("http://example.com", status=200)
        spider = MagicMock()

        with caplog.at_level(logging.WARNING):
            result = middleware.process_response(request, response, spider)

        # Should return the response unchanged
        assert result is response
        # Proxy should NOT be marked as failed
        assert proxy not in middleware._proxy_fail_counts

    def test_process_response_ignores_response_without_proxy(self, caplog):
        """process_response should skip if request has no proxy meta."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://proxy1:8080"],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        # No proxy meta set
        response = Response("http://example.com", status=403)
        spider = MagicMock()

        with caplog.at_level(logging.WARNING):
            result = middleware.process_response(request, response, spider)

        # Should return the response
        assert result is response
        # No fail counts should be recorded
        assert len(middleware._proxy_fail_counts) == 0

    def test_process_request_direct_connection_when_all_proxies_removed(self, caplog):
        """process_request should log ERROR and connect directly when all proxies removed."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=1  # Set to 1 for quick removal
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        # First, remove the proxy by failing it
        exception = ConnectionRefusedError("Connection refused")
        with caplog.at_level(logging.ERROR):
            middleware.process_exception(request, spider, exception)

        # Now proxy list should be empty
        assert len(middleware.proxy_list) == 0

        # Create a new request
        new_request = Request("http://example2.com")

        with caplog.at_level(logging.ERROR):
            middleware.process_request(new_request, spider)

        # Should log an ERROR about all proxies being removed
        assert any(
            record.levelno == logging.ERROR
            and "all proxies have been removed" in record.message.lower()
            for record in caplog.records
        )
        # Should not set proxy meta (direct connection)
        assert "proxy" not in new_request.meta

    def test_multiple_failures_increment_counter(self):
        """Multiple failures should increment the fail counter."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")

        # Fail twice
        middleware.process_exception(request, spider, exception)
        middleware.process_exception(request, spider, exception)

        # Counter should be 2
        assert middleware._proxy_fail_counts[proxy] == 2
        # Proxy should still be in list
        assert proxy in middleware.proxy_list

    def test_different_proxies_tracked_separately(self):
        """Different proxies should have separate failure counters."""
        proxy1 = "http://proxy1:8080"
        proxy2 = "http://proxy2:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy1, proxy2],
            proxy_max_fail=3
        )
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")

        # Fail proxy1 twice
        request1 = Request("http://example1.com")
        request1.meta["proxy"] = proxy1
        middleware.process_exception(request1, spider, exception)
        middleware.process_exception(request1, spider, exception)

        # Fail proxy2 once
        request2 = Request("http://example2.com")
        request2.meta["proxy"] = proxy2
        middleware.process_exception(request2, spider, exception)

        # Counters should be separate
        assert middleware._proxy_fail_counts[proxy1] == 2
        assert middleware._proxy_fail_counts[proxy2] == 1
        # Both proxies should still be in list
        assert proxy1 in middleware.proxy_list
        assert proxy2 in middleware.proxy_list

    def test_response_and_exception_failures_combined(self):
        """Failures from both process_response and process_exception should combine."""
        proxy = "http://proxy1:8080"
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=[proxy],
            proxy_max_fail=3
        )
        request = Request("http://example.com")
        request.meta["proxy"] = proxy
        spider = MagicMock()

        exception = ConnectionRefusedError("Connection refused")
        response_403 = Response("http://example.com", status=403)

        # Fail via exception once
        middleware.process_exception(request, spider, exception)

        # Fail via 403 response once
        middleware.process_response(request, response_403, spider)

        # Counter should be 2 (combined)
        assert middleware._proxy_fail_counts[proxy] == 2

    def test_initial_fail_counts_dict(self):
        """Middleware should initialize with empty fail counts."""
        middleware = ProxyMiddleware(
            proxy_enabled=True,
            proxy_list=["http://proxy1:8080"],
            proxy_max_fail=3
        )
        # Should have an empty dict for tracking failures
        assert hasattr(middleware, "_proxy_fail_counts")
        assert middleware._proxy_fail_counts == {}
