"""Tests for huginn/notify/anomaly.py — check_spider_failure."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from huginn.notify.anomaly import check_spider_failure


def _make_run(status: str, error_message: str | None = None) -> MagicMock:
    run = MagicMock()
    run.status = status
    run.error_message = error_message
    run.started_at = datetime.now(timezone.utc)
    return run


class TestCheckSpiderFailure:
    def test_three_consecutive_failures_trigger_notification(self):
        """Exactly FAILURE_THRESHOLD consecutive failures should send a notification."""
        rows = [
            _make_run("failed", "timeout"),
            _make_run("failed", "timeout"),
            _make_run("failed", "timeout"),
        ]
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = rows

            check_spider_failure("test_spider")

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["type"] == "spider_failure"
        assert "test_spider" in call_kwargs["title"]
        assert "3" in call_kwargs["title"]
        assert "test_spider" in call_kwargs["body"]
        assert call_kwargs["source"] == "test_spider"

    def test_two_consecutive_failures_no_notification(self):
        """Fewer than FAILURE_THRESHOLD failures should NOT trigger a notification."""
        rows = [
            _make_run("failed", "err"),
            _make_run("failed", "err"),
        ]
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = rows

            check_spider_failure("test_spider")

        mock_send.assert_not_called()

    def test_mixed_statuses_no_notification(self):
        """If not all recent runs failed, no notification is sent."""
        rows = [
            _make_run("failed", "err"),
            _make_run("success"),
            _make_run("failed", "err"),
        ]
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = rows

            check_spider_failure("test_spider")

        mock_send.assert_not_called()

    def test_no_runs_no_notification(self):
        """No runs at all should not trigger notification."""
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = []

            check_spider_failure("test_spider")

        mock_send.assert_not_called()

    def test_db_query_failure_does_not_raise(self):
        """DB failure should log ERROR but never raise."""
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session_cls.return_value.__enter__ = MagicMock(
                side_effect=Exception("DB unavailable")
            )

            # Should not raise
            check_spider_failure("test_spider")

        mock_send.assert_not_called()

    def test_notification_body_contains_error_message(self):
        """Notification body should include the most recent error message."""
        rows = [
            _make_run("failed", "Connection reset"),
            _make_run("failed", "Timeout"),
            _make_run("failed", "DNS error"),
        ]
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = rows

            check_spider_failure("my_spider")

        call_kwargs = mock_send.call_args[1]
        assert "Connection reset" in call_kwargs["body"]

    def test_notification_body_handles_no_error_message(self):
        """When runs have no error_message, body should still be informative."""
        rows = [
            _make_run("failed", None),
            _make_run("failed", None),
            _make_run("failed", None),
        ]
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.scalars.return_value.all.return_value = rows

            check_spider_failure("my_spider")

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["body"] is not None
