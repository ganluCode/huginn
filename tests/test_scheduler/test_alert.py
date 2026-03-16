"""Tests for huginn.scheduler.alert module."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from huginn.scheduler.alert import send_alert


class TestSendAlert:
    """Tests for send_alert function."""

    def test_empty_webhook_url_returns_early(self):
        """send_alert returns early when alert_webhook_url is empty."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = ""

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                send_alert("test_spider", "Error occurred", "run-123")

                # HTTP client should not be created
                mock_client_class.assert_not_called()

    def test_sends_post_with_correct_payload(self):
        """send_alert sends POST request with correct payload structure."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.return_value = mock_response

                send_alert("test_spider", "Error occurred", "run-123")

                # Verify POST was called
                mock_client.post.assert_called_once()

                # Verify call arguments
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "https://example.com/webhook"

                # Verify payload structure
                payload = call_args[1]["json"]
                assert payload["event"] == "spider_failed"
                assert payload["spider_name"] == "test_spider"
                assert payload["error_message"] == "Error occurred"
                assert payload["run_id"] == "run-123"
                assert "timestamp" in payload
                assert isinstance(payload["timestamp"], str)

    def test_http_timeout_is_10_seconds(self):
        """send_alert sets HTTP request timeout to 10 seconds."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.return_value = mock_response

                send_alert("test_spider", "Error", "run-123")

                # Verify timeout is 10 seconds
                call_kwargs = mock_client.post.call_args[1]
                assert call_kwargs["timeout"] == 10

    def test_network_error_logs_warning_no_exception(self, caplog):
        """send_alert logs WARNING on network error, does not raise exception."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.side_effect = httpx.ConnectError("Connection refused")

                # Should not raise exception
                send_alert("test_spider", "Error occurred", "run-123")

                # Should log warning
                assert "Failed to send alert" in caplog.text
                assert "Connection refused" in caplog.text

    def test_non_2xx_status_logs_warning_no_exception(self, caplog):
        """send_alert logs WARNING on non-2xx response, does not raise exception."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.is_success = False  # Set is_success property

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.return_value = mock_response

                # Should not raise exception
                send_alert("test_spider", "Error occurred", "run-123")

                # Should log warning
                assert "Webhook returned non-2xx status" in caplog.text
                assert "500" in caplog.text

    def test_success_2xx_logs_debug(self, caplog):
        """send_alert logs DEBUG on successful alert delivery."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.is_success = True  # Set is_success property

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.return_value = mock_response

                # Capture DEBUG level logs
                with caplog.at_level(logging.DEBUG):
                    send_alert("test_spider", "Error occurred", "run-123")

                # Should log debug
                assert "Alert sent successfully" in caplog.text

    def test_http_timeout_logs_warning(self, caplog):
        """send_alert logs WARNING on HTTP timeout, does not raise exception."""
        with patch("huginn.scheduler.alert.settings") as mock_settings:
            mock_settings.alert_webhook_url = "https://example.com/webhook"

            with patch("huginn.scheduler.alert.httpx.Client") as mock_client_class:
                mock_client = mock_client_class.return_value.__enter__.return_value
                mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

                # Should not raise exception
                send_alert("test_spider", "Error occurred", "run-123")

                # Should log warning
                assert "Failed to send alert" in caplog.text
                assert "Request timed out" in caplog.text
