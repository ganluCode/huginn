"""Scheduler manager for managing APScheduler lifecycle and spider jobs.

This module provides the SchedulerManager class which:
1. Loads enabled spiders from spider_registry
2. Registers cron-based scheduled jobs
3. Manages scheduler lifecycle (start/stop/reload)
4. Handles graceful updates when spider configurations change
"""

import logging

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from huginn.core.config import settings
from huginn.core.db import SyncSessionLocal
from huginn.core.models import SpiderRegistry

from huginn.scheduler import cron
from huginn.scheduler.runner import run_spider

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manager for APScheduler lifecycle and spider job management.

    This class wraps APScheduler to provide:
    - Automatic loading of enabled spiders from database
    - Cron-based scheduling using spider_registry.schedule
    - Dynamic reload when spider configurations change
    - Configurable max workers for concurrent job execution

    Example:
        >>> manager = SchedulerManager()
        >>> manager.start()
        >>> # ... scheduler runs ...
        >>> manager.reload()  # When spider configs change
        >>> manager.stop()
    """

    def __init__(self, max_workers: int | None = None) -> None:
        """Initialize the scheduler manager.

        Args:
            max_workers: Maximum number of concurrent jobs. Defaults to
                settings.scheduler_max_workers if not provided.
        """
        self._max_workers = max_workers or settings.scheduler_max_workers

        # Create scheduler with thread pool executor
        executors = {
            "default": {
                "type": "threadpool",
                "max_workers": self._max_workers,
            }
        }
        self.scheduler = BackgroundScheduler(executors=executors)

        # Track current spider jobs for reload diff
        self._current_spiders: dict[str, str] = {}  # spider_name -> schedule

    def start(self) -> None:
        """Start the scheduler and load enabled spiders from registry.

        Queries spider_registry for spiders where:
        - enabled = true
        - schedule IS NOT NULL

        For each matching spider, registers a cron-triggered job that calls
        run_spider(spider_name).

        Invalid cron expressions are logged as ERROR and skipped, allowing
        other valid spiders to be scheduled.

        Spider registry being empty is not an error - scheduler starts
        successfully with no jobs.

        Raises:
            Does not raise. All errors are caught and logged.
        """
        logger.info("Starting scheduler with max_workers=%d", self._max_workers)

        self.scheduler.start()

        # Load spiders from database
        with SyncSessionLocal() as session:
            result = session.execute(
                select(SpiderRegistry).filter(
                    SpiderRegistry.enabled == True,  # noqa: E712
                    SpiderRegistry.schedule.is_not(None),
                )
            )
            spiders = result.scalars().all()

            if not spiders:
                logger.info("No enabled spiders with schedule found in registry")
                return

            logger.info("Loading %d spider(s) from registry", len(spiders))

            for spider in spiders:
                self._add_spider_job(spider)

        logger.info("Scheduler started with %d job(s)", len(self.scheduler.get_jobs()))

    def _add_spider_job(self, spider: SpiderRegistry) -> None:
        """Add a scheduled job for a single spider.

        Parses the spider's cron expression and adds a job to the scheduler.
        Logs ERROR and skips the spider if the cron expression is invalid.

        Args:
            spider: SpiderRegistry instance with schedule attribute
        """
        try:
            cron_params = cron.parse_cron(spider.schedule)
        except ValueError as e:
            logger.error(
                "Invalid cron expression for spider '%s': '%s' - %s. Skipping.",
                spider.name,
                spider.schedule,
                e,
            )
            return

        # Add job to scheduler
        self.scheduler.add_job(
            run_spider,
            trigger=CronTrigger(**cron_params),
            id=spider.name,
            name=f"Run spider {spider.name}",
            replace_existing=True,
        )

        # Track for reload diff
        self._current_spiders[spider.name] = spider.schedule

        logger.info("Registered spider '%s' with schedule '%s'", spider.name, spider.schedule)

    def stop(self) -> None:
        """Stop the scheduler gracefully.

        Waits for all currently running jobs to complete before shutdown.

        Raises:
            Does not raise. All errors are caught and logged.
        """
        logger.info("Stopping scheduler")

        self.scheduler.shutdown(wait=True)

        logger.info("Scheduler stopped")

    def reload(self) -> None:
        """Reload spider jobs from registry, updating for configuration changes.

        Compares current scheduled jobs with spider_registry and:
        - Adds jobs for new enabled spiders
        - Removes jobs for deleted or disabled spiders
        - Updates jobs for spiders with changed schedules

        This method does NOT restart the scheduler - it modifies the
        running scheduler's job list in-place.

        Raises:
            Does not raise. All errors are caught and logged.
        """
        logger.info("Reloading spider jobs")

        # Load current spiders from database
        with SyncSessionLocal() as session:
            result = session.execute(
                select(SpiderRegistry).filter(
                    SpiderRegistry.enabled == True,  # noqa: E712
                    SpiderRegistry.schedule.is_not(None),
                )
            )
            spiders = result.scalars().all()

            # Build dict of current desired state
            desired_spiders: dict[str, str] = {
                spider.name: spider.schedule for spider in spiders
            }

        # Calculate diff
        current_names = set(self._current_spiders.keys())
        desired_names = set(desired_spiders.keys())

        to_add = desired_names - current_names
        to_remove = current_names - desired_names
        to_update = {
            name
            for name in current_names & desired_names
            if self._current_spiders[name] != desired_spiders[name]
        }

        # Apply changes
        for name in to_remove:
            self.scheduler.remove_job(name)
            del self._current_spiders[name]
            logger.info("Removed spider '%s' from scheduler", name)

        for name in to_add:
            spider = next(s for s in spiders if s.name == name)
            self._add_spider_job(spider)

        for name in to_update:
            # Remove old job and add new one with updated schedule
            self.scheduler.remove_job(name)
            spider = next(s for s in spiders if s.name == name)
            self._add_spider_job(spider)

        logger.info(
            "Reload complete: added=%d, removed=%d, updated=%d",
            len(to_add),
            len(to_remove),
            len(to_update),
        )
