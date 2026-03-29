"""Tests for huginn.notify.keyword — check_keyword function."""

import logging
import time
from datetime import datetime, UTC
from unittest.mock import MagicMock, call, patch

import pytest

from huginn.core.items import CollectedItem


def _make_item(
    source: str = "hackernews",
    title: str = "Test Item",
    data: dict | None = None,
) -> CollectedItem:
    return CollectedItem(
        source=source,
        category="tech",
        data=data if data is not None else {"title": title, "url": "https://example.com"},
        collected_at=datetime.now(UTC),
    )


def _make_monitor(
    keyword: str = "python",
    sources: list[str] | None = None,
    enabled: bool = True,
    webhook_url: str | None = None,
    monitor_id: int = 1,
) -> MagicMock:
    m = MagicMock()
    m.id = monitor_id
    m.keyword = keyword
    m.sources = sources
    m.enabled = enabled
    m.webhook_url = webhook_url
    return m


def _make_session_with_monitors(monitors: list) -> MagicMock:
    """Build a mock SyncSessionLocal context manager returning monitors from query."""
    session = MagicMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = monitors
    session.execute.return_value = query_result

    session_ctx = MagicMock()
    session_ctx.__enter__ = MagicMock(return_value=session)
    session_ctx.__exit__ = MagicMock(return_value=False)

    return MagicMock(return_value=session_ctx)


class TestCheckKeywordEmptyMonitors:
    """check_keyword when keyword_monitors table is empty."""

    def test_empty_monitors_no_notification_sent(self):
        """When monitors list is empty, send_notification is never called."""
        from huginn.notify import keyword as kw_module

        # Reset cache so DB is queried
        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        session_local = _make_session_with_monitors([])
        item = _make_item(title="Python news")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_not_called()

    def test_empty_monitors_db_queried_once_then_cached(self):
        """Empty monitor list is cached; DB is not queried on second call."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        session_local = _make_session_with_monitors([])
        item = _make_item(title="Python news")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification"),
        ):
            kw_module.check_keyword(item)
            kw_module.check_keyword(item)

        # SyncSessionLocal() was called only once (first call loads cache)
        assert session_local.call_count == 1


class TestCheckKeywordSourceFilter:
    """check_keyword source filtering logic."""

    def test_source_not_in_monitor_sources_skips(self):
        """Monitor with sources=['reddit'] skips an item from 'hackernews'."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="python", sources=["reddit"])
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(source="hackernews", title="Python is great")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_not_called()

    def test_empty_sources_matches_any_source(self):
        """Monitor with sources=None (or empty) matches items from any source."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="python", sources=None)
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(source="hackernews", title="Python is great")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_called_once()

    def test_source_in_monitor_sources_triggers(self):
        """Monitor with sources=['hackernews'] matches item from 'hackernews'."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="python", sources=["hackernews"])
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(source="hackernews", title="Python is great")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_called_once()


class TestCheckKeywordMatching:
    """check_keyword keyword matching logic."""

    def test_case_insensitive_match_in_title(self):
        """Keyword match in item.data['title'] is case-insensitive."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="PYTHON")
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(data={"title": "python news today", "url": "https://example.com"})

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_called_once()

    def test_match_in_data_text_fields(self):
        """Keyword match in other text fields of item.data triggers notification."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="fastapi")
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(
            data={"title": "New web framework", "description": "Built with FastAPI backend", "url": "x"}
        )

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_called_once()

    def test_no_match_does_not_trigger(self):
        """Item with no matching keyword does not trigger notification."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="rust")
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(data={"title": "Python is great", "url": "x"})

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        mock_send.assert_not_called()

    def test_multiple_keywords_each_triggers_notification(self):
        """Single item matching 2 different monitors triggers 2 notifications."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor1 = _make_monitor(keyword="python", monitor_id=1)
        monitor2 = _make_monitor(keyword="fastapi", monitor_id=2)
        session_local = _make_session_with_monitors([monitor1, monitor2])
        item = _make_item(data={"title": "Python FastAPI tutorial", "url": "x"})

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        assert mock_send.call_count == 2


class TestCheckKeywordNotificationFields:
    """Correct fields passed to send_notification."""

    def test_notification_type_is_keyword_hit(self):
        """send_notification is called with type='keyword_hit'."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="python")
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(source="hackernews", data={"title": "Python news", "url": "x"})

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        call_kwargs = mock_send.call_args
        assert call_kwargs[1].get("type", call_kwargs[0][0] if call_kwargs[0] else None) == "keyword_hit" or \
               mock_send.call_args[0][0] == "keyword_hit"

    def test_notification_source_matches_item_source(self):
        """send_notification source parameter matches item.source."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        monitor = _make_monitor(keyword="python")
        session_local = _make_session_with_monitors([monitor])
        item = _make_item(source="reddit", data={"title": "Python discussion", "url": "x"})

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
        ):
            kw_module.check_keyword(item)

        # source should be passed as keyword arg or positional
        args, kwargs = mock_send.call_args
        source_arg = kwargs.get("source") or (args[3] if len(args) > 3 else None)
        assert source_arg == "reddit"


class TestCheckKeywordCache:
    """Cache behavior: 5-minute TTL."""

    def test_cache_prevents_second_db_query_within_5_minutes(self):
        """Multiple calls within 5 minutes query DB only once."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        session_local = _make_session_with_monitors([])
        item = _make_item(title="test")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification"),
        ):
            kw_module.check_keyword(item)
            kw_module.check_keyword(item)
            kw_module.check_keyword(item)

        assert session_local.call_count == 1

    def test_cache_expires_after_5_minutes(self):
        """After 5 minutes, DB is queried again."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        session_local = _make_session_with_monitors([])
        item = _make_item(title="test")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification"),
        ):
            kw_module.check_keyword(item)
            # Simulate cache expiry
            kw_module._cache_time = time.monotonic() - 310  # > 5 minutes ago
            kw_module.check_keyword(item)

        assert session_local.call_count == 2


class TestCheckKeywordErrorHandling:
    """check_keyword error handling."""

    def test_db_error_logs_error_and_does_not_raise(self, caplog):
        """DB query failure logs ERROR, function does not raise."""
        from huginn.notify import keyword as kw_module

        kw_module._cache_time = 0.0
        kw_module._cache_monitors = []

        session_ctx = MagicMock()
        session_ctx.__enter__ = MagicMock(side_effect=Exception("DB connection failed"))
        session_ctx.__exit__ = MagicMock(return_value=False)
        session_local = MagicMock(return_value=session_ctx)

        item = _make_item(title="Python news")

        with (
            patch("huginn.notify.keyword.SyncSessionLocal", session_local),
            patch("huginn.notify.keyword.send_notification") as mock_send,
            caplog.at_level(logging.ERROR, logger="huginn.notify.keyword"),
        ):
            kw_module.check_keyword(item)

        assert any(r.levelno == logging.ERROR for r in caplog.records)
        mock_send.assert_not_called()
