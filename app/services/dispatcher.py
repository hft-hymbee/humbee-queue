"""
Notification Dispatcher
=======================
Handles fanout logic: receives a notification event and dispatches
individual Celery tasks per (channel × recipient) combination.

Usage:
    from services.dispatcher import NotificationDispatcher

    dispatcher = NotificationDispatcher(db_session)
    results = dispatcher.dispatch(
        event_type="ORDER_PLACED",
        channels=["EMAIL", "SMS"],
        recipients=["user@example.com", "+91xxx"],
        template_id="order.create.erw_angles",
        payload={...},
    )
"""

from typing import List, Optional
import re
from uuid import uuid4

from sqlalchemy.orm import Session

from core.celery_app import celery_app
from core.logging import get_logger
from domain.enums import NotificationChannel
from services.notification_service import NotificationService

logger = get_logger("service.dispatcher")

# Channel enum → Celery task name
CHANNEL_TASK_MAP = {
    NotificationChannel.EMAIL: "notification.send_email",
    NotificationChannel.SMS: "notification.send_sms",
    NotificationChannel.WHATSAPP: "notification.send_whatsapp",
    NotificationChannel.PUSH: "notification.send_push",
}

# Channel enum → Celery queue name
CHANNEL_QUEUE_MAP = {
    NotificationChannel.EMAIL: "email_queue",
    NotificationChannel.SMS: "sms_queue",
    NotificationChannel.WHATSAPP: "whatsapp_queue",
    NotificationChannel.PUSH: "push_queue",
}


class NotificationDispatcher:
    """
    Dispatches notification events to per-channel Celery queues.
    Creates a notification_history record per (channel × recipient) before dispatching.
    """

    def __init__(self, db: Optional[Session]):
        self.db = db

    def dispatch(
        self,
        event_type: str,
        channels: List[NotificationChannel],
        recipients: List[str],
        template_id: str,
        payload: dict,
        user_id: Optional[str] = None,
        subject: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Fan out notification to all (channel × recipient) combinations.

        Args:
            event_type: Event name (e.g., "ORDER_PLACED")
            channels: List of channels to send on
            recipients: List of recipient addresses
            template_id: Template identifier
            payload: Notification payload
            user_id: Optional user ID for tracking
            subject: Optional subject line (email/push)
            request_id: Optional idempotency key

        Returns:
            List of dicts with notification_id and channel for each dispatched notification
        """
        # Idempotency check: if request_id already has records, skip
        if request_id and self.db:
            existing = NotificationService.get_by_request_id(self.db, request_id)
            if existing:
                logger.info(
                    f"Request {request_id} already dispatched ({len(existing)} records), skipping",
                    extra={"request_id": request_id},
                )
                return [
                    {
                        "notification_id": str(r.id),
                        "channel": r.channel,
                        "status": r.status,
                        "skipped": True,
                    }
                    for r in existing
                ]

        results = []

        def _filter_recipients(channel: NotificationChannel, all_recipients: List[str]) -> List[str]:
            phone_regex = re.compile(r"^\+?\d{6,15}$")
            
            if channel == NotificationChannel.EMAIL:
                return [r for r in all_recipients if "@" in r]
            elif channel in (NotificationChannel.SMS, NotificationChannel.WHATSAPP):
                # Strict phone number matching so tokens don't leak into SMS
                return [r for r in all_recipients if phone_regex.match(r)]
            elif channel == NotificationChannel.PUSH:
                # Push tokens/user_ids shouldn't be emails or plain phone numbers
                return [r for r in all_recipients if "@" not in r and not phone_regex.match(r)]
            
            return all_recipients

        for channel in channels:
            valid_recipients = _filter_recipients(channel, recipients)
            for recipient in valid_recipients:
                notification_id = uuid4()
                task_name = CHANNEL_TASK_MAP.get(channel)
                queue_name = CHANNEL_QUEUE_MAP.get(channel)

                if not task_name:
                    logger.error(f"Unknown channel: {channel}")
                    continue

                # Create DB record
                if self.db:
                    NotificationService.create(
                        db=self.db,
                        id=notification_id,
                        event_type=event_type,
                        channel=channel.value,
                        recipient=recipient,
                        template_id=template_id,
                        user_id=user_id,
                        subject=subject,
                        payload=payload,
                        request_id=request_id,
                    )

                # Dispatch to Celery
                task_result = celery_app.send_task(
                    task_name,
                    kwargs={
                        "notification_id": str(notification_id),
                        "recipient": recipient,
                        "template_id": template_id,
                        "payload": payload,
                        "subject": subject,
                        "request_id": request_id,
                    },
                    queue=queue_name,
                )

                # Update celery_task_id in DB
                if self.db:
                    record = NotificationService.get_by_id(self.db, notification_id)
                    if record:
                        record.celery_task_id = task_result.id

                logger.info(
                    f"Dispatched {channel.value} notification",
                    extra={
                        "notification_id": str(notification_id),
                        "channel": channel.value,
                        "recipient": recipient,
                        "event_type": event_type,
                        "request_id": request_id,
                        "celery_task_id": task_result.id,
                    },
                )

                results.append({
                    "notification_id": str(notification_id),
                    "channel": channel.value,
                    "status": "QUEUED",
                })

        # Commit all DB records
        if self.db:
            self.db.commit()

        logger.info(
            f"Dispatch complete: {len(results)} notifications queued",
            extra={
                "event_type": event_type,
                "request_id": request_id,
                "total_dispatched": len(results),
            },
        )

        return results
