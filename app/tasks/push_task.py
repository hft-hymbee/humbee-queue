"""
Push Celery Task
================
Thin wrapper around PushChannel. For now, just marks the DB record as SENT
since the record itself IS the push notification.
"""


from uuid import UUID

from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.logging import get_logger
from channels.push.channel import PushChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.push")


@celery_app.task(
    name="notification.send_push",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    retry_backoff=True,
)
def send_push_notification(
    self,
    notification_id: str,
    recipient: str,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
):
    """Process a push notification (DB-only for now)."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "PUSH",
        "request_id": request_id,
    }

    logger.info("Push task received", extra=log_extra)

    with get_db_session() as db:
        if db:
            record = NotificationService.get_by_id(db, UUID(notification_id))
            if record and record.status == NotificationStatus.SENT.value:
                logger.info("Already processed, skipping", extra=log_extra)
                return {"status": "skipped", "reason": "already_sent"}

            NotificationService.mark_processing(db, UUID(notification_id))

    try:
        channel = PushChannel(
            notification_id=notification_id,
            recipient=recipient,
            template_id=template_id,
            payload=payload,
            subject=subject,
        )
        result = channel.send()

        with get_db_session() as db:
            if db:
                NotificationService.mark_sent(
                    db, UUID(notification_id), provider_response=result
                )

        logger.info("Push task completed", extra={**log_extra, "status": "SENT"})
        return result

    except ValueError as val_err:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(val_err),
                    retry_count=self.request.retries,
                )
        logger.error(f"Push validation failed: {val_err}", extra={**log_extra, "status": "FAILED"})
        return {"status": "failed", "reason": "validation_error", "message": str(val_err)}

    except Exception as exc:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(exc),
                    retry_count=self.request.retries,
                )

        logger.error(f"Push task failed: {exc}", extra={**log_extra, "status": "FAILED"})
        raise
