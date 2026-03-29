"""Anomaly detection: spider failure and data volume anomaly checks."""

import logging
import os

from sqlalchemy import select

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
