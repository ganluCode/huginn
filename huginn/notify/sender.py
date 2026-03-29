"""HTTP notification senders for Feishu and generic webhooks."""

import logging

import httpx

from huginn.core.config import settings
from huginn.core.db import SyncSessionLocal
from huginn.core.models import Notification

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


def send_notification(
    type: str,
    title: str,
    body: str | None,
    source: str | None,
    webhook_url: str | None = None,
) -> None:
    """Unified notification entry: persist to DB and dispatch to configured channels.

    Inserts a Notification record (sent=False), then sends via available channels.
    Updates sent=True if at least one channel succeeds. Never raises.

    Webhook URL priority for Feishu: webhook_url param > settings.feishu_webhook_url.
    ALERT_WEBHOOK_URL is read from settings.alert_webhook_url independently.

    Args:
        type: Notification type (e.g. 'keyword_hit', 'spider_failure', 'data_anomaly').
        title: Short notification title.
        body: Notification body text. May be None.
        source: Data source name that triggered the notification. May be None.
        webhook_url: Override Feishu webhook URL. If None, falls back to settings.
    """
    # Step 1: Insert record with sent=False
    notification_id: int | None = None
    try:
        notification = Notification(
            type=type,
            title=title,
            body=body,
            source=source,
            sent=False,
        )
        with SyncSessionLocal() as session:
            session.add(notification)
            session.commit()
            session.refresh(notification)
            notification_id = notification.id
    except Exception as exc:
        logger.error("send_notification: DB write failed — %s", exc)
        return

    # Step 2: Determine effective webhook URLs
    feishu_url = webhook_url or settings.feishu_webhook_url
    alert_url = settings.alert_webhook_url

    # Step 3: Dispatch to configured channels
    any_sent = False

    if feishu_url:
        if send_feishu(feishu_url, title, body or ""):
            any_sent = True

    if alert_url:
        payload = {"type": type, "title": title, "body": body, "source": source}
        if send_webhook(alert_url, payload):
            any_sent = True

    # Step 4: Update sent=True if at least one channel succeeded
    if any_sent and notification_id is not None:
        try:
            with SyncSessionLocal() as session:
                record = session.get(Notification, notification_id)
                if record is not None:
                    record.sent = True
                    session.commit()
        except Exception as exc:
            logger.error(
                "send_notification: DB update sent failed for id=%s — %s",
                notification_id,
                exc,
            )
