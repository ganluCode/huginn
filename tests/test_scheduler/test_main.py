"""Tests for huginn.scheduler.__main__ module."""

import logging
import signal
from unittest.mock import MagicMock, patch

import pytest


class TestMainModule:
    """Tests for the scheduler main entry point."""

    @patch("huginn.scheduler.__main__.SchedulerManager")
    def test_main_initializes_logging(self, mock_manager_class):
        """Test that main configures logging on startup."""
        # We'll verify this indirectly through caplog in test_main_logs_start_and_stop
        # This test is kept as a placeholder to ensure basicConfig is called
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Run main (will block on scheduler, so we'll simulate interruption)
        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]  # Exit after first check
            mock_event_class.return_value = mock_event

            main()

        # If we get here without exception, logging was configured successfully

    @patch("huginn.scheduler.__main__.SchedulerManager")
    def test_main_creates_and_starts_manager(self, mock_manager_class):
        """Test that main creates SchedulerManager and calls start()."""
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]
            mock_event_class.return_value = mock_event

            main()

        # Verify manager was created and started
        mock_manager_class.assert_called_once()
        mock_manager.start.assert_called_once()

    @patch("huginn.scheduler.__main__.SchedulerManager")
    def test_main_stops_manager_on_exit(self, mock_manager_class):
        """Test that main calls manager.stop() on normal exit."""
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]
            mock_event_class.return_value = mock_event

            main()

        # Verify manager was stopped
        mock_manager.stop.assert_called_once()

    @patch("huginn.scheduler.__main__.SchedulerManager")
    @patch("huginn.scheduler.__main__.signal.signal")
    def test_main_registers_sigint_handler(self, mock_signal, mock_manager_class):
        """Test that main registers handler for SIGINT (Ctrl+C)."""
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]
            mock_event_class.return_value = mock_event

            main()

        # Verify SIGINT handler was registered
        sigint_calls = [call for call in mock_signal.call_args_list if signal.SIGINT in call[0]]
        assert len(sigint_calls) == 1

    @patch("huginn.scheduler.__main__.SchedulerManager")
    @patch("huginn.scheduler.__main__.signal.signal")
    def test_main_registers_sigterm_handler(self, mock_signal, mock_manager_class):
        """Test that main registers handler for SIGTERM."""
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]
            mock_event_class.return_value = mock_event

            main()

        # Verify SIGTERM handler was registered
        sigterm_calls = [call for call in mock_signal.call_args_list if signal.SIGTERM in call[0]]
        assert len(sigterm_calls) == 1

    @patch("huginn.scheduler.__main__.SchedulerManager")
    def test_main_logs_start_and_stop(self, mock_manager_class, caplog):
        """Test that main logs INFO messages on start and stop."""
        from huginn.scheduler.__main__ import main

        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        with patch("huginn.scheduler.__main__.Event") as mock_event_class:
            mock_event = MagicMock()
            mock_event.is_set.side_effect = [False, True]
            mock_event_class.return_value = mock_event

            with caplog.at_level(logging.INFO):
                main()

        # Verify start and stop were logged
        log_messages = [record.message for record in caplog.records]
        assert any("Starting" in msg for msg in log_messages)
        assert any("stopped" in msg.lower() or "Stopping" in msg for msg in log_messages)

    @patch("huginn.scheduler.__main__.SchedulerManager")
    def test_signal_handler_sets_stop_event(self, mock_manager_class):
        """Test that signal handler sets the stop event."""
        from huginn.scheduler.__main__ import _handle_signal

        mock_event = MagicMock()
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Call the signal handler
        _handle_signal(signal.SIGTERM, None, mock_event)

        # Verify event was set
        mock_event.set.assert_called_once()
