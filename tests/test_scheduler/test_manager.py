"""Tests for huginn.scheduler.manager module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from huginn.core.models import SpiderRegistry
from huginn.scheduler.manager import SchedulerManager


class TestSchedulerManager:
    """Tests for SchedulerManager class."""

    def test_start_registers_spiders_from_registry(self):
        """start() queries spider_registry and registers CronTrigger jobs for enabled spiders."""
        # Create test spiders
        spider1 = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )
        spider2 = SpiderRegistry(
            name="spider2",
            engine="scrapy",
            category="finance",
            schedule="0 9 * * 1-5",
            enabled=True,
        )
        spider3_disabled = SpiderRegistry(
            name="spider3_disabled",
            engine="scrapy",
            category="social",
            schedule="0 * * * *",
            enabled=False,
        )

        # Mock database session
        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Mock execute to return only enabled spiders with schedule
            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = [spider1, spider2]
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            # Mock run_spider to avoid actual execution
            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

                # Verify two jobs were registered (only enabled spiders with schedule)
                assert len(manager.scheduler.get_jobs()) == 2

                # Verify job IDs match spider names
                job_ids = {job.id for job in manager.scheduler.get_jobs()}
                assert job_ids == {"spider1", "spider2"}

    def test_start_logs_loaded_spiders(self, caplog):
        """start() logs INFO with spider names and schedules."""
        spider = SpiderRegistry(
            name="test_spider",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = [spider]
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                with caplog.at_level("INFO"):
                    manager.start()

                    # Verify log contains spider name and schedule
                    log_messages = [record.message for record in caplog.records]
                    assert any("test_spider" in msg and "*/30 * * * *" in msg for msg in log_messages)

    def test_start_skips_invalid_cron(self, caplog):
        """start() logs ERROR and skips spiders with invalid cron expressions."""
        spider_valid = SpiderRegistry(
            name="valid_spider",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )
        spider_invalid = SpiderRegistry(
            name="invalid_spider",
            engine="scrapy",
            category="finance",
            schedule="invalid cron",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Return both spiders
            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = [spider_valid, spider_invalid]
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                with caplog.at_level("ERROR"):
                    manager.start()

                    # Verify only valid spider was registered
                    assert len(manager.scheduler.get_jobs()) == 1
                    assert manager.scheduler.get_jobs()[0].id == "valid_spider"

                    # Verify error was logged
                    error_logs = [record.message for record in caplog.records if record.levelname == "ERROR"]
                    assert len(error_logs) > 0
                    assert any("invalid_spider" in msg for msg in error_logs)

    def test_start_with_empty_registry(self):
        """start() works correctly when spider_registry is empty."""
        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Return empty list
            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            # Should not raise any error
            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

                # Scheduler should be running with no jobs
                assert manager.scheduler.running
                assert len(manager.scheduler.get_jobs()) == 0

    def test_start_skips_spiders_without_schedule(self):
        """start() skips enabled spiders that have NULL schedule."""
        # Note: In SQL query, spiders with NULL schedule are filtered out
        # So they won't even be returned from the query
        spider_no_schedule = SpiderRegistry(
            name="no_schedule_spider",
            engine="scrapy",
            category="tech",
            schedule=None,
            enabled=True,
        )

        # The SQL query filters out NULL schedules, so result should be empty
        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

                # No jobs should be registered
                assert len(manager.scheduler.get_jobs()) == 0

    def test_stop_stops_scheduler_gracefully(self):
        """stop() gracefully stops the scheduler with wait=True."""
        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

            assert manager.scheduler.running

            manager.stop()

            assert not manager.scheduler.running

    def test_reload_adds_new_spiders(self):
        """reload() adds new spiders to the scheduler."""
        # Start with one spider
        spider1 = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )
        spider2 = SpiderRegistry(
            name="spider2",
            engine="scrapy",
            category="finance",
            schedule="0 9 * * 1-5",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                # First call returns only spider1
                mock_execute_result_1 = MagicMock()
                mock_execute_result_1.scalars.return_value.all.return_value = [spider1]

                # Second call (reload) returns both spiders
                mock_execute_result_2 = MagicMock()
                mock_execute_result_2.scalars.return_value.all.return_value = [spider1, spider2]

                mock_session.execute.side_effect = [mock_execute_result_1, mock_execute_result_2]

                manager.start()
                assert len(manager.scheduler.get_jobs()) == 1

                manager.reload()

                # Both spiders should be scheduled
                assert len(manager.scheduler.get_jobs()) == 2
                job_ids = {job.id for job in manager.scheduler.get_jobs()}
                assert job_ids == {"spider1", "spider2"}

    def test_reload_removes_deleted_spiders(self):
        """reload() removes spiders that are no longer in registry."""
        spider1 = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )
        spider2 = SpiderRegistry(
            name="spider2",
            engine="scrapy",
            category="finance",
            schedule="0 9 * * 1-5",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                # First call returns both spiders
                mock_execute_result_1 = MagicMock()
                mock_execute_result_1.scalars.return_value.all.return_value = [spider1, spider2]

                # Second call (reload) returns only spider1
                mock_execute_result_2 = MagicMock()
                mock_execute_result_2.scalars.return_value.all.return_value = [spider1]

                mock_session.execute.side_effect = [mock_execute_result_1, mock_execute_result_2]

                manager.start()
                assert len(manager.scheduler.get_jobs()) == 2

                manager.reload()

                # Only spider1 should remain
                assert len(manager.scheduler.get_jobs()) == 1
                assert manager.scheduler.get_jobs()[0].id == "spider1"

    def test_reload_updates_schedule_changes(self):
        """reload() updates triggers when spider schedules change."""
        spider = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )

        spider_updated = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="0 9 * * 1-5",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                # First call returns spider with original schedule
                mock_execute_result_1 = MagicMock()
                mock_execute_result_1.scalars.return_value.all.return_value = [spider]

                # Second call returns spider with updated schedule
                mock_execute_result_2 = MagicMock()
                mock_execute_result_2.scalars.return_value.all.return_value = [spider_updated]

                mock_session.execute.side_effect = [mock_execute_result_1, mock_execute_result_2]

                manager.start()

                # Get original trigger
                original_job = manager.scheduler.get_jobs()[0]
                # Check that the original schedule had */30 for minute
                assert "*/30" in str(original_job.trigger)
                assert "9" not in str(original_job.trigger)

                manager.reload()

                # Verify trigger was updated
                updated_job = manager.scheduler.get_jobs()[0]
                # Check that the new schedule has 0 for minute and 9 for hour
                assert "minute='0'" in str(updated_job.trigger)
                assert "hour='9'" in str(updated_job.trigger)
                assert "1-5" in str(updated_job.trigger)

    def test_reload_handles_spider_becoming_disabled(self):
        """reload() removes spiders when they become disabled."""
        spider = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                # First call returns enabled spider
                mock_execute_result_1 = MagicMock()
                mock_execute_result_1.scalars.return_value.all.return_value = [spider]

                # Second call returns empty (spider disabled)
                mock_execute_result_2 = MagicMock()
                mock_execute_result_2.scalars.return_value.all.return_value = []

                mock_session.execute.side_effect = [mock_execute_result_1, mock_execute_result_2]

                manager.start()
                assert len(manager.scheduler.get_jobs()) == 1

                manager.reload()

                # Spider should be removed from scheduler
                assert len(manager.scheduler.get_jobs()) == 0

    def test_max_workers_config_is_respected(self):
        """scheduler_max_workers config controls maximum concurrent jobs."""
        spider = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = [spider]
            mock_session.execute.return_value = mock_execute_result

            # Pass max_workers=2 directly
            manager = SchedulerManager(max_workers=2)

            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

                # Verify the manager has max_workers=2
                assert manager._max_workers == 2

    def test_start_with_multiple_valid_and_invalid_spiders(self):
        """start() processes mix of valid and invalid spiders correctly."""
        spider1 = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
        )
        spider2_invalid = SpiderRegistry(
            name="spider2_invalid",
            engine="scrapy",
            category="finance",
            schedule="bad cron",
            enabled=True,
        )
        spider3 = SpiderRegistry(
            name="spider3",
            engine="scrapy",
            category="social",
            schedule="0 9 * * 1-5",
            enabled=True,
        )

        with patch("huginn.scheduler.manager.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Return all spiders (including invalid one)
            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.all.return_value = [spider1, spider2_invalid, spider3]
            mock_session.execute.return_value = mock_execute_result

            manager = SchedulerManager()

            with patch("huginn.scheduler.manager.run_spider"):
                manager.start()

                # Only valid spiders should be registered
                assert len(manager.scheduler.get_jobs()) == 2
                job_ids = {job.id for job in manager.scheduler.get_jobs()}
                assert job_ids == {"spider1", "spider3"}
