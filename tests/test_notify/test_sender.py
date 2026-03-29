"""Tests for huginn.notify.sender module — send_feishu and send_webhook."""

import logging
from unittest.mock import Mock, patch

import httpx
import pytest


class TestSendFeishu:
    """Tests for send_feishu function."""

    def test_success_returns_true(self):
        """send_feishu returns True when HTTP response is 2xx."""
        from huginn.notify.sender import send_feishu

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            result = send_feishu("https://example.com/hook", "Test Title", "Test Content")

        assert result is True

    def test_non_2xx_returns_false(self):
        """send_feishu returns False on non-2xx HTTP response."""
        from huginn.notify.sender import send_feishu

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            result = send_feishu("https://example.com/hook", "Test Title", "Test Content")

        assert result is False

    def test_network_error_returns_false(self):
        """send_feishu returns False on network exception without raising."""
        from huginn.notify.sender import send_feishu

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")

            result = send_feishu("https://example.com/hook", "Test Title", "Test Content")

        assert result is False

    def test_timeout_error_returns_false(self):
        """send_feishu returns False on timeout without raising."""
        from huginn.notify.sender import send_feishu

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")

            result = send_feishu("https://example.com/hook", "Test Title", "Test Content")

        assert result is False

    def test_feishu_interactive_card_format(self):
        """send_feishu sends a valid Feishu interactive card JSON payload."""
        from huginn.notify.sender import send_feishu

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            send_feishu("https://example.com/hook", "Alert Title", "Alert Body")

            call_kwargs = mock_client.post.call_args[1]
            payload = call_kwargs["json"]

        assert payload["msg_type"] == "interactive"
        card = payload["card"]
        assert "header" in card
        assert card["header"]["title"]["content"] == "Alert Title"
        assert "elements" in card
        # Check content is present in the elements
        content_found = any(
            "Alert Body" in str(el) for el in card["elements"]
        )
        assert content_found

    def test_uses_10_second_timeout(self):
        """send_feishu uses 10 second timeout for HTTP request."""
        from huginn.notify.sender import send_feishu

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            send_feishu("https://example.com/hook", "Title", "Content")

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["timeout"] == 10

    def test_logs_warning_on_failure(self, caplog):
        """send_feishu logs WARNING with webhook_url on network failure."""
        from huginn.notify.sender import send_feishu

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")

            with caplog.at_level(logging.WARNING, logger="huginn.notify.sender"):
                send_feishu("https://example.com/hook", "Title", "Content")

        assert any("https://example.com/hook" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_logs_warning_on_non_2xx(self, caplog):
        """send_feishu logs WARNING with webhook_url on non-2xx response."""
        from huginn.notify.sender import send_feishu

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            with caplog.at_level(logging.WARNING, logger="huginn.notify.sender"):
                send_feishu("https://example.com/hook", "Title", "Content")

        assert any("https://example.com/hook" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestSendWebhook:
    """Tests for send_webhook function."""

    def test_success_returns_true(self):
        """send_webhook returns True when HTTP response is 2xx."""
        from huginn.notify.sender import send_webhook

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            result = send_webhook("https://example.com/hook", {"key": "value"})

        assert result is True

    def test_non_2xx_returns_false(self):
        """send_webhook returns False on non-2xx HTTP response."""
        from huginn.notify.sender import send_webhook

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            result = send_webhook("https://example.com/hook", {"key": "value"})

        assert result is False

    def test_network_error_returns_false(self):
        """send_webhook returns False on network exception without raising."""
        from huginn.notify.sender import send_webhook

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")

            result = send_webhook("https://example.com/hook", {"key": "value"})

        assert result is False

    def test_posts_json_payload(self):
        """send_webhook sends the exact payload as JSON."""
        from huginn.notify.sender import send_webhook

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200
        payload = {"event": "test", "data": "value", "count": 42}

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            send_webhook("https://example.com/hook", payload)

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["json"] == payload

    def test_uses_10_second_timeout(self):
        """send_webhook uses 10 second timeout for HTTP request."""
        from huginn.notify.sender import send_webhook

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            send_webhook("https://example.com/hook", {})

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["timeout"] == 10

    def test_logs_warning_on_failure(self, caplog):
        """send_webhook logs WARNING with webhook_url on failure."""
        from huginn.notify.sender import send_webhook

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")

            with caplog.at_level(logging.WARNING, logger="huginn.notify.sender"):
                send_webhook("https://example.com/hook", {"key": "value"})

        assert any("https://example.com/hook" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_logs_warning_on_non_2xx(self, caplog):
        """send_webhook logs WARNING with webhook_url on non-2xx response."""
        from huginn.notify.sender import send_webhook

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("huginn.notify.sender.httpx.Client") as mock_client_class:
            mock_client = mock_client_class.return_value.__enter__.return_value
            mock_client.post.return_value = mock_response

            with caplog.at_level(logging.WARNING, logger="huginn.notify.sender"):
                send_webhook("https://example.com/hook", {"key": "value"})

        assert any("https://example.com/hook" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
