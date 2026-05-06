"""
Email Celery Task
=================
Thin wrapper around EmailChannel. Handles:
- Idempotency check (skip if already sent)
- DB status updates (PROCESSING → SENT / FAILED)
- Retries with exponential backoff
"""

import smtplib
from uuid import UUID

from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.logging import get_logger
from channels.email.channel import EmailChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.email")


@celery_app.task(
    name="notification.send_email",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    autoretry_for=(ConnectionError, TimeoutError, smtplib.SMTPException),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def send_email_notification(
    self,
    notification_id: str,
    recipient: str,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
):
    """Send an email notification."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "EMAIL",
        "recipient": recipient,
        "template_id": template_id,
        "request_id": request_id,
    }

    logger.info("Email task received", extra=log_extra)

    with get_db_session() as db:
        if db:
            # Idempotency check
            record = NotificationService.get_by_id(db, UUID(notification_id))
            if record and record.status == NotificationStatus.SENT.value:
                logger.info("Already sent, skipping", extra=log_extra)
                return {"status": "skipped", "reason": "already_sent"}

            NotificationService.mark_processing(db, UUID(notification_id))

    try:
        channel = EmailChannel(
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

        logger.info("Email task completed successfully", extra={**log_extra, "status": "SENT"})
        return result

    except ValueError as val_err:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(val_err),
                    retry_count=self.request.retries,
                )
        logger.error(f"Email validation failed: {val_err}", extra={**log_extra, "status": "FAILED"})
        return {"status": "failed", "reason": "validation_error", "message": str(val_err)}

    except Exception as exc:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db,
                    UUID(notification_id),
                    error_message=str(exc),
                    retry_count=self.request.retries,
                )

        logger.error(
            f"Email task failed: {exc}",
            extra={**log_extra, "status": "FAILED", "error_message": str(exc), "retry_count": self.request.retries},
        )
        raise
