"""
SMS Celery Task
===============
Thin wrapper around SMSChannel. Handles:
- Idempotency check
- DB status updates
- Retries with exponential backoff
"""

import requests
from uuid import UUID

from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.exceptions import Provider5xxError, RateLimitError
from core.logging import get_logger
from channels.sms.channel import SMSChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.sms")


@celery_app.task(
    name="notification.send_sms",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    autoretry_for=(ConnectionError, TimeoutError, Provider5xxError, RateLimitError),
    retry_backoff=30,
    retry_backoff_max=1800,
    retry_jitter=True,
)
def send_sms_notification(
    self,
    notification_id: str,
    recipient: str,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
):
    """Send an SMS notification via Telspiel."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "SMS",
        "recipient": recipient,
        "template_id": template_id,
        "request_id": request_id,
    }

    logger.info("SMS task received", extra=log_extra)

    with get_db_session() as db:
        if db:
            record = NotificationService.get_by_id(db, UUID(notification_id))
            if record and record.status == NotificationStatus.SENT.value:
                logger.info("Already sent, skipping", extra=log_extra)
                return {"status": "skipped", "reason": "already_sent"}

            NotificationService.mark_processing(db, UUID(notification_id))

    try:
        channel = SMSChannel(
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

        logger.info("SMS task completed successfully", extra={**log_extra, "status": "SENT"})
        return result

    except ValueError as val_err:
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=str(val_err),
                    retry_count=self.request.retries,
                )
        logger.error(f"SMS validation failed: {val_err}", extra={**log_extra, "status": "FAILED"})
        return {"status": "failed", "reason": "validation_error", "message": str(val_err)}

    except (ConnectionError, TimeoutError, Provider5xxError, RateLimitError) as exc:
        # Mark as failed in DB to update error message and retry count
        # Celery autoretry_for will handle the actual retry logic and backoff
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=f"Retryable error: {exc}",
                    retry_count=self.request.retries,
                )
        
        logger.warning(
            f"SMS task failed (retryable): {exc}. Celery will autoretry. (Attempt {self.request.retries + 1}/{self.max_retries})",
            extra={**log_extra, "retry_count": self.request.retries + 1}
        )
        raise exc

    except requests.exceptions.RequestException as exc:
        # Non-retryable request errors (e.g., 4xx excluding 429)
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=f"Non-retryable request error: {exc}",
                    retry_count=self.request.retries,
                )

        logger.error(f"SMS task failed (non-retryable): {exc}", extra={**log_extra, "status": "FAILED", "error_message": str(exc)})
        return {"status": "failed", "error": str(exc)}

    except Exception as exc:
        # Unexpected errors
        with get_db_session() as db:
            if db:
                NotificationService.mark_failed(
                    db, UUID(notification_id),
                    error_message=f"Unexpected error: {exc}",
                    retry_count=self.request.retries,
                )

        logger.error(f"SMS task failed (unexpected): {exc}", extra={**log_extra, "status": "FAILED", "error_message": str(exc)})
        raise exc
