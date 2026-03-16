"""Webhook alert notifications for spider failures.

This module provides functionality to send HTTP POST webhook notifications
when spider runs fail. Webhooks are configured via the alert_webhook_url
setting and include structured JSON payload with failure details.
"""

import logging

from datetime import datetime, timezone

import httpx

from huginn.core.config import settings

logger = logging.getLogger(__name__)

# Event type for spider failure alerts
SPIDER_FAILED_EVENT = "spider_failed"


def send_alert(spider_name: str, error_message: str, run_id: str) -> None:
    """Send a failure alert webhook notification.

    Sends an HTTP POST request to the configured webhook URL with structured
    payload containing spider failure details. If no webhook URL is configured,
    the function returns early without making any HTTP request.

    All HTTP errors (network failures, timeouts, non-2xx responses) are caught
    and logged as warnings without raising exceptions, ensuring that alert
    delivery failures never crash the spider runner.

    Args:
        spider_name: Name of the spider that failed.
        error_message: Error message or exception details.
        run_id: Unique identifier for the spider run.

    Returns:
        None

    Side effects:
        - Sends HTTP POST request if webhook URL is configured
        - Logs DEBUG on successful delivery
        - Logs WARNING on any delivery failure

    Examples:
        >>> send_alert("hackernews", "Connection timeout", "run-123")
        # Sends POST to webhook with failure details
    """
    webhook_url = settings.alert_webhook_url

    # Early return if no webhook configured
    if not webhook_url:
        return

    # Build alert payload
    payload = {
        "event": SPIDER_FAILED_EVENT,
        "spider_name": spider_name,
        "error_message": error_message,
        "run_id": run_id,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

    try:
        with httpx.Client() as client:
            response = client.post(
                webhook_url,
                json=payload,
                timeout=10,  # 10 second timeout
            )

        if not response.is_success:
            logger.warning(
                "Webhook returned non-2xx status: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            logger.debug(
                "Alert sent successfully for spider '%s' (run_id: %s)",
                spider_name,
                run_id,
            )

    except (httpx.HTTPError, OSError) as e:
        # Catch all httpx errors and socket-level errors
        logger.warning("Failed to send alert for spider '%s': %s", spider_name, e)
