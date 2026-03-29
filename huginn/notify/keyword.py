"""Keyword monitoring: check a CollectedItem against configured keyword monitors."""

import logging
import time

from sqlalchemy import select

from huginn.core.db import SyncSessionLocal
from huginn.core.items import CollectedItem
from huginn.core.models import KeywordMonitor
from huginn.notify.sender import send_notification

logger = logging.getLogger(__name__)

# In-memory cache: list of enabled KeywordMonitor rows and the time they were loaded.
_cache_monitors: list = []
_cache_time: float = 0.0
_CACHE_TTL = 300.0  # 5 minutes


def _load_monitors() -> list:
    """Load enabled keyword monitors from DB, using a 5-minute cache.

    Returns the cached list if it was loaded within the last 5 minutes.
    On DB failure, logs ERROR and returns an empty list.
    """
    global _cache_monitors, _cache_time

    now = time.monotonic()
    if now - _cache_time < _CACHE_TTL:
        return _cache_monitors

    try:
        with SyncSessionLocal() as session:
            result = session.execute(
                select(KeywordMonitor).where(KeywordMonitor.enabled.is_(True))
            )
            monitors = list(result.scalars().all())
        _cache_monitors = monitors
        _cache_time = time.monotonic()
        return _cache_monitors
    except Exception as exc:
        logger.error("check_keyword: failed to load keyword monitors — %s", exc)
        return []


def _extract_text_fields(data: dict) -> str:
    """Extract all string values from a dict (one level deep) joined as a single string."""
    parts = []
    for value in data.values():
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def check_keyword(item: CollectedItem) -> None:
    """Check a CollectedItem against enabled keyword monitors and send notifications.

    Loads keyword monitors from DB with a 5-minute in-memory cache. For each enabled
    monitor, checks whether the item's source matches the monitor's source filter, then
    performs a case-insensitive keyword search across item.data text fields. On a match,
    calls send_notification with type='keyword_hit'. Never raises.

    Args:
        item: The collected item to check.
    """
    try:
        monitors = _load_monitors()
    except Exception as exc:
        logger.error("check_keyword: unexpected error loading monitors — %s", exc)
        return

    if not monitors:
        return

    # Build searchable text from item.data
    item_text = _extract_text_fields(item.data).lower()

    for monitor in monitors:
        # Source filter: if monitor.sources is non-empty, item.source must be in the list
        if monitor.sources and item.source not in monitor.sources:
            continue

        keyword_lower = monitor.keyword.lower()
        if keyword_lower in item_text:
            title_text = item.data.get("title", item.source)
            send_notification(
                type="keyword_hit",
                title=f"关键词命中: {monitor.keyword}",
                body=f"来源: {item.source}\n标题: {title_text}\n关键词: {monitor.keyword}",
                source=item.source,
                webhook_url=monitor.webhook_url or None,
            )
