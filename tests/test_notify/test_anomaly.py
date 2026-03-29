"""Tests for huginn/notify/anomaly.py — check_spider_failure and check_data_anomaly."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from huginn.notify.anomaly import check_data_anomaly, check_spider_failure


def _make_data_row(item_count: int, days_ago: float) -> MagicMock:
    """Create a mock row for check_data_anomaly with started_at and item_count."""
    row = MagicMock()
    row.started_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    row.item_count = item_count
    return row


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


class TestCheckDataAnomaly:
    def _patch(self, rows):
        mock_session_cls = MagicMock()
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.all.return_value = rows
        return mock_session_cls

    def test_significant_drop_triggers_notification(self):
        """current_count=0 with historical avg=100 should trigger data_anomaly alert."""
        rows = [_make_data_row(100, days_ago=d) for d in range(7, 0, -1)]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=0)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["type"] == "data_anomaly"
        assert "my_spider" in call_kwargs["title"]
        assert "0" in call_kwargs["body"]
        assert call_kwargs["source"] == "my_spider"

    def test_insufficient_history_no_notification(self):
        """When data spans less than 7 days, no notification is sent."""
        # All rows within last 6 days
        rows = [_make_data_row(100, days_ago=d) for d in [1, 2, 3, 4, 5, 6]]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=0)

        mock_send.assert_not_called()

    def test_no_history_no_notification(self):
        """No history at all should not trigger a notification."""
        mock_session_cls = self._patch([])

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=0)

        mock_send.assert_not_called()

    def test_low_historical_avg_no_notification(self):
        """Historical average <= 10 should not trigger a notification."""
        rows = [_make_data_row(5, days_ago=d) for d in range(7, 0, -1)]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=0)

        mock_send.assert_not_called()

    def test_count_above_threshold_no_notification(self):
        """current_count >= avg * ANOMALY_THRESHOLD should not trigger a notification."""
        rows = [_make_data_row(100, days_ago=d) for d in range(7, 0, -1)]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=60)

        mock_send.assert_not_called()

    def test_count_exactly_at_threshold_no_notification(self):
        """current_count == avg * ANOMALY_THRESHOLD should not trigger (not strictly less)."""
        rows = [_make_data_row(100, days_ago=d) for d in range(7, 0, -1)]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=50)

        mock_send.assert_not_called()

    def test_db_query_failure_does_not_raise(self):
        """DB failure should log ERROR but never raise."""
        with patch("huginn.notify.anomaly.SyncSessionLocal") as mock_session_cls, \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            mock_session_cls.return_value.__enter__ = MagicMock(
                side_effect=Exception("DB unavailable")
            )
            check_data_anomaly("my_spider", current_count=0)

        mock_send.assert_not_called()

    def test_notification_body_contains_counts(self):
        """Notification body must include both current count and historical average."""
        rows = [_make_data_row(100, days_ago=d) for d in range(7, 0, -1)]
        mock_session_cls = self._patch(rows)

        with patch("huginn.notify.anomaly.SyncSessionLocal", mock_session_cls), \
             patch("huginn.notify.anomaly.send_notification") as mock_send:
            check_data_anomaly("my_spider", current_count=10)

        call_kwargs = mock_send.call_args[1]
        body = call_kwargs["body"]
        assert "10" in body
        assert "100" in body
