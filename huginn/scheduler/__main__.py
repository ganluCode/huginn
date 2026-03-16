"""Command-line entry point for the Huginn scheduler.

This module provides `python -m huginn.scheduler` command to start
the scheduler daemon. It handles graceful shutdown on SIGINT/SIGTERM.
"""

import logging
import signal
import sys
from threading import Event

from huginn.scheduler.manager import SchedulerManager

logger = logging.getLogger(__name__)


def _handle_signal(signum: int, frame, stop_event: Event) -> None:
    """Handle shutdown signals (SIGINT, SIGTERM).

    Args:
        signum: The signal number received.
        frame: The current stack frame (unused).
        stop_event: Threading event to set to signal shutdown.
    """
    logger.info("Received signal %d, initiating graceful shutdown", signum)
    stop_event.set()


def main() -> None:
    """Main entry point for the scheduler daemon.

    This function:
    1. Configures logging
    2. Creates a SchedulerManager instance
    3. Starts the scheduler (loads enabled spiders)
    4. Registers signal handlers for SIGINT/SIGTERM
    5. Waits until shutdown signal is received
    6. Stops the scheduler gracefully

    Raises:
        Does not raise. All errors are caught and logged.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    logger.info("Starting Huginn scheduler daemon")

    # Create scheduler manager
    manager = SchedulerManager()

    # Start the scheduler (loads spiders from registry)
    manager.start()

    # Create event for graceful shutdown
    stop_event = Event()

    # Register signal handlers
    signal.signal(
        signal.SIGINT,
        lambda sig, frame: _handle_signal(sig, frame, stop_event),
    )
    signal.signal(
        signal.SIGTERM,
        lambda sig, frame: _handle_signal(sig, frame, stop_event),
    )

    logger.info("Scheduler running, waiting for shutdown signal")

    # Wait for shutdown signal
    stop_event.wait()

    # Stop the scheduler gracefully
    manager.stop()

    logger.info("Scheduler daemon stopped")


if __name__ == "__main__":
    main()
