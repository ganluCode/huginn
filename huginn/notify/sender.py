"""HTTP notification senders for Feishu and generic webhooks."""

import logging

import httpx

logger = logging.getLogger(__name__)


def send_feishu(webhook_url: str, title: str, content: str) -> bool:
    """Send a Feishu interactive card notification via webhook.

    Constructs a Feishu interactive card message and sends it via HTTP POST.
    Returns True on success (2xx response), False on any failure.
    Never raises exceptions.

    Args:
        webhook_url: Feishu bot webhook URL.
        title: Card header title text.
        content: Card body content (supports Feishu Markdown).

    Returns:
        True if the request succeeded (2xx), False otherwise.
    """
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content,
                    },
                }
            ],
        },
    }

    try:
        with httpx.Client() as client:
            response = client.post(webhook_url, json=payload, timeout=10)

        if not response.is_success:
            logger.warning(
                "send_feishu: non-2xx response from %s — status=%s body=%s",
                webhook_url,
                response.status_code,
                response.text,
            )
            return False

        return True

    except (httpx.HTTPError, OSError) as exc:
        logger.warning("send_feishu: failed to send to %s — %s", webhook_url, exc)
        return False


def send_webhook(webhook_url: str, payload: dict) -> bool:
    """Send a JSON payload to a generic webhook endpoint via HTTP POST.

    Returns True on success (2xx response), False on any failure.
    Never raises exceptions.

    Args:
        webhook_url: Target webhook URL.
        payload: JSON-serializable dict to POST.

    Returns:
        True if the request succeeded (2xx), False otherwise.
    """
    try:
        with httpx.Client() as client:
            response = client.post(webhook_url, json=payload, timeout=10)

        if not response.is_success:
            logger.warning(
                "send_webhook: non-2xx response from %s — status=%s body=%s",
                webhook_url,
                response.status_code,
                response.text,
            )
            return False

        return True

    except (httpx.HTTPError, OSError) as exc:
        logger.warning("send_webhook: failed to send to %s — %s", webhook_url, exc)
        return False
