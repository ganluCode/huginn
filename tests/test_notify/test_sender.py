"""Tests for huginn.notify.sender module — send_feishu, send_webhook, send_notification."""

import logging
from unittest.mock import MagicMock, Mock, patch

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


def _make_session_mock(notification_id: int = 1):
    """Build a mock SyncSessionLocal context manager that returns a usable session."""
    notification_obj = MagicMock()
    notification_obj.id = notification_id
    notification_obj.sent = False

    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", notification_id))
    session.get = MagicMock(return_value=notification_obj)

    session_ctx = MagicMock()
    session_ctx.__enter__ = MagicMock(return_value=session)
    session_ctx.__exit__ = MagicMock(return_value=False)

    session_local = MagicMock(return_value=session_ctx)
    return session_local, session, notification_obj


class TestSendNotification:
    """Tests for send_notification unified entry function."""

    def test_inserts_db_record_with_sent_false(self):
        """send_notification inserts a Notification record with sent=False."""
        from huginn.notify.sender import send_notification

        session_local, session, _ = _make_session_mock()

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
        ):
            mock_settings.feishu_webhook_url = ""
            mock_settings.alert_webhook_url = ""
            send_notification("keyword_hit", "Test Title", "Test body", "hackernews")

        session.add.assert_called_once()
        session.commit.assert_called()

    def test_no_channels_configured_only_writes_db(self):
        """When no webhook URLs are configured, only writes to DB without error."""
        from huginn.notify.sender import send_notification

        session_local, session, _ = _make_session_mock()

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_feishu") as mock_feishu,
            patch("huginn.notify.sender.send_webhook") as mock_wh,
        ):
            mock_settings.feishu_webhook_url = ""
            mock_settings.alert_webhook_url = ""
            send_notification("keyword_hit", "Title", "Body", "source")

        mock_feishu.assert_not_called()
        mock_wh.assert_not_called()

    def test_feishu_called_when_feishu_url_configured(self):
        """FEISHU_WEBHOOK_URL non-empty triggers send_feishu."""
        from huginn.notify.sender import send_notification

        session_local, _, _ = _make_session_mock()

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_feishu", return_value=True) as mock_feishu,
        ):
            mock_settings.feishu_webhook_url = "https://feishu.example.com/hook"
            mock_settings.alert_webhook_url = ""
            send_notification("spider_failure", "Title", "Body", "hackernews")

        mock_feishu.assert_called_once_with(
            "https://feishu.example.com/hook", "Title", "Body"
        )

    def test_webhook_called_when_alert_url_configured(self):
        """ALERT_WEBHOOK_URL non-empty triggers send_webhook."""
        from huginn.notify.sender import send_notification

        session_local, _, _ = _make_session_mock()

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_webhook", return_value=True) as mock_wh,
        ):
            mock_settings.feishu_webhook_url = ""
            mock_settings.alert_webhook_url = "https://alert.example.com/hook"
            send_notification("data_anomaly", "Title", "Body", "github_trending")

        mock_wh.assert_called_once()
        call_args = mock_wh.call_args
        assert call_args[0][0] == "https://alert.example.com/hook"

    def test_param_webhook_url_overrides_feishu_env(self):
        """webhook_url parameter takes priority over settings.feishu_webhook_url."""
        from huginn.notify.sender import send_notification

        session_local, _, _ = _make_session_mock()

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_feishu", return_value=True) as mock_feishu,
        ):
            mock_settings.feishu_webhook_url = "https://default.feishu.com/hook"
            mock_settings.alert_webhook_url = ""
            send_notification(
                "keyword_hit",
                "Title",
                "Body",
                "source",
                webhook_url="https://custom.feishu.com/hook",
            )

        mock_feishu.assert_called_once_with(
            "https://custom.feishu.com/hook", "Title", "Body"
        )

    def test_sent_updated_to_true_when_any_channel_succeeds(self):
        """sent=True is set in DB when at least one channel succeeds."""
        from huginn.notify.sender import send_notification

        session_local, session, notification_obj = _make_session_mock(notification_id=42)

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_feishu", return_value=True),
        ):
            mock_settings.feishu_webhook_url = "https://feishu.example.com/hook"
            mock_settings.alert_webhook_url = ""
            send_notification("keyword_hit", "Title", "Body", "source")

        session.get.assert_called()
        assert notification_obj.sent is True

    def test_sent_stays_false_when_all_channels_fail(self):
        """sent stays False when all channels fail to send."""
        from huginn.notify.sender import send_notification

        session_local, session, notification_obj = _make_session_mock(notification_id=7)

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            patch("huginn.notify.sender.send_feishu", return_value=False),
        ):
            mock_settings.feishu_webhook_url = "https://feishu.example.com/hook"
            mock_settings.alert_webhook_url = ""
            send_notification("keyword_hit", "Title", "Body", "source")

        assert notification_obj.sent is False

    def test_db_failure_logs_error_and_does_not_raise(self, caplog):
        """DB write failure logs ERROR and function does not raise."""
        from huginn.notify.sender import send_notification

        session_ctx = MagicMock()
        session_ctx.__enter__ = MagicMock(side_effect=Exception("DB connection failed"))
        session_ctx.__exit__ = MagicMock(return_value=False)
        session_local = MagicMock(return_value=session_ctx)

        with (
            patch("huginn.notify.sender.SyncSessionLocal", session_local),
            patch("huginn.notify.sender.settings") as mock_settings,
            caplog.at_level(logging.ERROR, logger="huginn.notify.sender"),
        ):
            mock_settings.feishu_webhook_url = ""
            mock_settings.alert_webhook_url = ""
            send_notification("keyword_hit", "Title", "Body", "source")

        assert any(r.levelno == logging.ERROR for r in caplog.records)
