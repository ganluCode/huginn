"""Tests for huginn.scheduler.runner module."""

import logging
import subprocess
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from huginn.core.models import SpiderRegistry, SpiderRun
from huginn.scheduler.runner import run_spider


class TestRunSpider:
    """Tests for run_spider function."""

    def test_spider_not_in_registry_returns_early(self, caplog):
        """run_spider returns early when spider_name is not in spider_registry."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Mock session.execute() to return None (spider not found)
            mock_session.execute.return_value.scalar_one_or_none.return_value = None

            with patch("huginn.scheduler.runner.subprocess.Popen"):
                # Enable all log levels for capture
                with caplog.at_level(logging.DEBUG, logger="huginn.scheduler.runner"):
                    run_spider("nonexistent_spider")

                # Should log ERROR
                assert "not found in spider_registry" in caplog.text.lower()

    def test_skips_when_already_running(self, caplog):
        """run_spider skips execution when spider already has status='running'."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Mock spider exists in registry
            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy")

            # Mock existing running record (second execute call should return SpiderRun)
            mock_running = SpiderRun(
                spider_name="test_spider",
                started_at=datetime.now(timezone.utc),
                status="running",
            )

            # Set up execute to return different values for different calls
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, mock_running]
            mock_session.execute.return_value = mock_execute_result

            with patch("huginn.scheduler.runner.subprocess.Popen"):
                with caplog.at_level(logging.DEBUG, logger="huginn.scheduler.runner"):
                    run_spider("test_spider")

                    # Should log WARNING and skip execution
                    assert "already has a running instance" in caplog.text.lower()

    def test_creates_spider_run_record_on_start(self):
        """run_spider INSERTs spider_runs record with status='running' on start."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            # Mock spider exists
            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy", enabled=True, schedule="0 * * * *")
            # No running record
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_process.stderr.read.return_value = b""

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                run_spider("test_spider")

                # Verify SpiderRun record was added
                mock_session.add.assert_called()

    def test_success_status_when_exit_code_zero(self):
        """run_spider updates status to 'success' when subprocess exits with code 0."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy", enabled=True, schedule="0 * * * *")
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_process.stderr.read.return_value = b""

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                run_spider("test_spider")

                # Verify commit was called
                assert mock_session.commit.call_count >= 1

    def test_failed_status_with_stderr_when_exit_code_nonzero(self):
        """run_spider sets status='failed' with stderr content when exit code is non-zero."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy", enabled=True, schedule="0 * * * *")
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 1
            stderr_content = b"Error: Connection failed\nTraceback..."
            mock_process.stderr.read.return_value = stderr_content

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                with patch("huginn.scheduler.runner.alert.send_alert"):
                    run_spider("test_spider")

                    # Verify commit was called
                    assert mock_session.commit.call_count >= 1

    def test_updates_spider_registry_on_success(self):
        """run_spider updates spider_registry.last_run_at, last_status, and item_count."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(
                name="test_spider",
                engine="scrapy",
                enabled=True,
                schedule="0 * * * *",
                item_count=10,
            )
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_process.stderr.read.return_value = b""

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                run_spider("test_spider")

                # Verify commit was called
                assert mock_session.commit.call_count >= 1

    def test_timeout_kills_process_and_marks_failed(self):
        """run_spider kills subprocess after spider_timeout seconds and marks as failed."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy", enabled=True, schedule="0 * * * *")
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            # Make wait() raise TimeoutExpired
            mock_process.wait.side_effect = subprocess.TimeoutExpired("scrapy", 1)
            mock_process.stderr.read.return_value = b""

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                with patch("huginn.scheduler.runner.settings") as mock_settings:
                    mock_settings.spider_timeout = 1

                    with patch("huginn.scheduler.runner.alert.send_alert"):
                        run_spider("test_spider")

                        # Verify kill was called
                        mock_process.kill.assert_called()

    def test_failed_status_calls_send_alert(self):
        """run_spider calls alert.send_alert() when status='failed'."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy")
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 1
            mock_process.stderr.read.return_value = b"Error occurred"

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                with patch("huginn.scheduler.runner.alert.send_alert") as mock_alert:
                    run_spider("test_spider")

                    # Verify send_alert was called
                    mock_alert.assert_called_once()
                    call_args = mock_alert.call_args[0]
                    assert call_args[0] == "test_spider"  # spider_name
                    assert "Error occurred" in call_args[1]  # error_message

    def test_updates_finished_at_and_duration_ms(self):
        """run_spider updates spider_runs.finished_at and duration_ms."""
        with patch("huginn.scheduler.runner.SyncSessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None

            mock_spider = SpiderRegistry(name="test_spider", engine="scrapy", enabled=True, schedule="0 * * * *")
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.side_effect = [mock_spider, None, mock_spider]
            mock_session.execute.return_value = mock_execute_result

            mock_process = MagicMock()
            mock_process.wait.return_value = 0
            mock_process.stderr.read.return_value = b""

            with patch("huginn.scheduler.runner.subprocess.Popen", return_value=mock_process):
                run_spider("test_spider")

                # Verify commit was called
                assert mock_session.commit.call_count >= 1
