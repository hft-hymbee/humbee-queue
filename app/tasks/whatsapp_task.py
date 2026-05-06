"""
WhatsApp Celery Task
====================
Thin wrapper around WhatsAppChannel. Handles:
- Idempotency check
- DB status updates
- Retries with exponential backoff
"""

from uuid import UUID

from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.logging import get_logger
from channels.whatsapp.channel import WhatsAppChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.whatsapp")


@celery_app.task(
    name="notification.send_whatsapp",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def send_whatsapp_notification(
    self,
    notification_id: str,
    recipient: str,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
):
    """Send a WhatsApp notification via aggregator."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "WHATSAPP",
        "recipient": recipient,
        "template_id": template_id,
        "request_id": request_id,
    }

    logger.info("WhatsApp task received", extra=log_extra)

    with get_db_session() as db:
        if db:
            record = NotificationService.get_by_id(db, UUID(notification_id))
            if record and record.status == NotificationStatus.SENT.value:
                logger.info("Already sent, skipping", extra=log_extra)
                return {"status": "skipped", "reason": "already_sent"}

            NotificationService.mark_processing(db, UUID(notification_id))

    try:
        channel = WhatsAppChannel(
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

        logger.info("WhatsApp task completed", extra={**log_extra, "status": "SENT"})
        return result

    except NotImplementedError as exc:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(exc),
                    retry_count=0,
                )
        logger.warning(f"WhatsApp provider not implemented: {exc}", extra=log_extra)
        return {"status": "not_implemented", "error": str(exc)}

    except Exception as exc:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(exc),
                    retry_count=self.request.retries,
                )

        logger.error(f"WhatsApp task failed: {exc}", extra={**log_extra, "status": "FAILED"})
        raise
