"""Spider runner module for executing Scrapy spiders in subprocesses.

This module provides the run_spider function which:
1. Validates spider exists in spider_registry
2. Checks for already-running instances
3. Creates spider_runs record with status='running'
4. Executes 'scrapy crawl' in a subprocess
5. Updates spider_runs and spider_registry on completion
6. Handles timeouts and sends alerts on failure
"""

import logging
import subprocess
from datetime import datetime, timezone

from sqlalchemy import select

from huginn.core.config import settings
from huginn.core.db import SyncSessionLocal
from huginn.core.models import SpiderRegistry, SpiderRun

from huginn.scheduler import alert

logger = logging.getLogger(__name__)


def run_spider(spider_name: str) -> None:
    """Execute a Scrapy spider in a subprocess with full state tracking.

    This function manages the complete lifecycle of a spider run:
    - Validates the spider exists in spider_registry
    - Checks for duplicate running instances
    - Creates a spider_runs record with status='running'
    - Executes the spider in a subprocess with timeout
    - Updates spider_runs and spider_registry on completion
    - Sends webhook alerts on failure

    Args:
        spider_name: Name of the spider to run (must exist in spider_registry)

    Returns:
        None

    Raises:
        Does not raise exceptions. All errors are caught and logged.

    Side effects:
        - INSERTs/UPDATEs spider_runs table
        - UPDATEs spider_registry table
        - Sends HTTP POST webhook on failure (if configured)
        - Executes 'scrapy crawl <spider_name>' subprocess

    Examples:
        >>> run_spider("hackernews")
        # Executes 'scrapy crawl hackernews' in subprocess
    """
    with SyncSessionLocal() as session:
        # Step 1: Check spider exists in registry
        spider = session.execute(
            select(SpiderRegistry).filter_by(name=spider_name)
        ).scalar_one_or_none()

        if spider is None:
            logger.error("Spider '%s' not found in spider_registry, skipping execution", spider_name)
            return

        # Step 2: Check for already-running instance
        running_record = session.execute(
            select(SpiderRun)
            .filter_by(spider_name=spider_name, status="running")
            .order_by(SpiderRun.started_at.desc())
        ).scalar_one_or_none()

        if running_record is not None:
            logger.warning(
                "Spider '%s' already has a running instance (started at %s), skipping execution",
                spider_name,
                running_record.started_at,
            )
            return

        # Step 3: Create spider_runs record with status='running'
        run_record = SpiderRun(
            spider_name=spider_name,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        session.add(run_record)
        session.commit()
        session.refresh(run_record)

        run_id = str(run_record.id)

        logger.info("Starting spider '%s' (run_id: %s)", spider_name, run_id)

        # Step 4: Execute spider in subprocess
        process = None
        error_message = None
        status = "success"

        try:
            process = subprocess.Popen(
                ["scrapy", "crawl", spider_name],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            # Wait with timeout
            try:
                return_code = process.wait(timeout=settings.spider_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                error_message = f"Spider timeout after {settings.spider_timeout} seconds"
                logger.error("Spider '%s' timed out after %d seconds", spider_name, settings.spider_timeout)
                status = "failed"

            if status != "failed":
                if return_code == 0:
                    status = "success"
                    logger.info("Spider '%s' completed successfully", spider_name)
                else:
                    status = "failed"
                    # Capture stderr (first 2000 chars)
                    stderr_bytes = process.stderr.read()
                    stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:2000]
                    error_message = stderr_text if stderr_text else f"Exit code: {return_code}"
                    logger.error(
                        "Spider '%s' failed with exit code %d: %s",
                        spider_name,
                        return_code,
                        error_message,
                    )

        except Exception as e:
            status = "failed"
            error_message = f"Unexpected error: {e!s}"
            logger.exception("Unexpected error running spider '%s': %s", spider_name, e)

        # Step 5: Update spider_runs record
        run_record.finished_at = datetime.now(timezone.utc)
        run_record.status = status
        run_record.duration_ms = int(
            (run_record.finished_at - run_record.started_at).total_seconds() * 1000
        )
        if error_message:
            run_record.error_message = error_message

        # Step 6: Update spider_registry
        spider.last_run_at = run_record.finished_at
        spider.last_status = status
        if status == "success":
            # Increment item count (placeholder - actual count comes from Scrapy stats)
            spider.item_count = (spider.item_count or 0) + 0

        session.commit()

        # Step 7: Send alert on failure
        if status == "failed":
            alert.send_alert(spider_name, error_message or "Unknown error", run_id)
