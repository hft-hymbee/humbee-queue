"""
InApp Celery Task
=================
Thin wrapper around InAppChannel. For now, just marks the DB record as SENT
since the record itself IS the in-app notification.
"""

from uuid import UUID

from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.logging import get_logger
from channels.inapp.channel import InAppChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.inapp")


@celery_app.task(
    name="notification.send_inapp",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    retry_backoff=True,
)
def send_inapp_notification(
    self,
    notification_id: str,
    recipient: str,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
):
    """Process an in-app notification (DB-only for now)."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "INAPP",
        "request_id": request_id,
    }

    logger.info("InApp task received", extra=log_extra)

    with get_db_session() as db:
        if db:
            record = NotificationService.get_by_id(db, UUID(notification_id))
            if record and record.status == NotificationStatus.SENT.value:
                logger.info("Already processed, skipping", extra=log_extra)
                return {"status": "skipped", "reason": "already_sent"}

            NotificationService.mark_processing(db, UUID(notification_id))

    try:
        channel = InAppChannel(
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

        logger.info("InApp task completed", extra={**log_extra, "status": "SENT"})
        return result

    except ValueError as val_err:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(val_err),
                    retry_count=self.request.retries,
                )
        logger.error(f"InApp validation failed: {val_err}", extra={**log_extra, "status": "FAILED"})
        return {"status": "failed", "reason": "validation_error", "message": str(val_err)}

    except Exception as exc:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(exc),
                    retry_count=self.request.retries,
                )

        logger.error(f"InApp task failed: {exc}", extra={**log_extra, "status": "FAILED"})
        raise
