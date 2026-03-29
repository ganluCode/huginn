"""Anomaly detection: spider failure and data volume anomaly checks."""

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from huginn.core.db import SyncSessionLocal
from huginn.core.models import SpiderRun
from huginn.notify.sender import send_notification

logger = logging.getLogger(__name__)

# Default thresholds (can be overridden via environment variables)
FAILURE_THRESHOLD: int = int(os.environ.get("FAILURE_THRESHOLD", "3"))
ANOMALY_THRESHOLD: float = float(os.environ.get("ANOMALY_THRESHOLD", "0.5"))


def check_spider_failure(spider_name: str) -> None:
    """Check if a spider has consecutively failed and send an alert if threshold is met.

    Queries the spider_runs table for the most recent FAILURE_THRESHOLD runs of the
    given spider. If all of them have status 'failed', triggers a spider_failure
    notification. Never raises.

    Args:
        spider_name: The name of the spider to check.
    """
    try:
        with SyncSessionLocal() as session:
            rows = session.execute(
                select(SpiderRun)
                .where(SpiderRun.spider_name == spider_name)
                .order_by(SpiderRun.started_at.desc())
                .limit(FAILURE_THRESHOLD)
            ).scalars().all()
    except Exception as exc:
        logger.error(
            "check_spider_failure: DB query failed for spider=%s — %s", spider_name, exc
        )
        return

    if len(rows) < FAILURE_THRESHOLD:
        return

    consecutive_failures = sum(1 for r in rows if r.status == "failed")
    if consecutive_failures < FAILURE_THRESHOLD:
        return

    # Collect error messages from the failed runs (most recent first)
    error_messages = [r.error_message for r in rows if r.error_message]
    recent_error = error_messages[0] if error_messages else "No error message recorded"

    send_notification(
        type="spider_failure",
        title=f"Spider 连续失败告警: {spider_name} (连续失败 {consecutive_failures} 次)",
        body=f"Spider: {spider_name}\n连续失败次数: {consecutive_failures}\n最近错误: {recent_error}",
        source=spider_name,
    )


def check_data_anomaly(spider_name: str, current_count: int) -> None:
    """Check if a spider's item count has dropped significantly below its historical average.

    Queries spider_runs for the past 7 days to compute the average item_count.
    If there is less than 7 days of history, or the average is <= 10, no alert
    is triggered. When current_count < avg * ANOMALY_THRESHOLD, a data_anomaly
    notification is sent. Never raises.

    Args:
        spider_name: The name of the spider to check.
        current_count: The number of items collected in the current run.
    """
    seven_days_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
    try:
        with SyncSessionLocal() as session:
            rows = session.execute(
                select(SpiderRun.started_at, SpiderRun.item_count)
                .where(SpiderRun.spider_name == spider_name)
                .where(SpiderRun.started_at >= seven_days_ago)
                .where(SpiderRun.status == "success")
                .order_by(SpiderRun.started_at.asc())
            ).all()
    except Exception as exc:
        logger.error(
            "check_data_anomaly: DB query failed for spider=%s — %s", spider_name, exc
        )
        return

    if not rows:
        return

    # Check for at least 7 days of spread: earliest run must be at least 7 days ago
    earliest = rows[0].started_at
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=timezone.utc)
    if (datetime.now(tz=timezone.utc) - earliest) < timedelta(days=7):
        return

    avg = sum(r.item_count for r in rows) / len(rows)
    if avg <= 10:
        return

    if current_count < avg * ANOMALY_THRESHOLD:
        send_notification(
            type="data_anomaly",
            title=f"Spider 数据量骤降告警: {spider_name}",
            body=(
                f"Spider: {spider_name}\n"
                f"本次采集数量: {current_count}\n"
                f"历史平均数量: {avg:.1f}\n"
                f"触发阈值: {ANOMALY_THRESHOLD * 100:.0f}%"
            ),
            source=spider_name,
        )
