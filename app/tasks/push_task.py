"""
Push Celery Task
================
Thin wrapper around PushChannel. Handles:
- Idempotency check
- DB status updates
- Retries with exponential backoff
"""

import requests
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from core.celery_app import celery_app
from core.config import settings
from core.database import get_db_session
from core.exceptions import Provider5xxError, RateLimitError, ProviderFailedError
from core.logging import get_logger
from channels.push.channel import PushChannel
from domain.enums import NotificationStatus
from services.notification_service import NotificationService

logger = get_logger("task.push")

# How long to wait for the DB record to become visible before giving up.
# Under the fixed dispatcher, this guard should virtually never trigger.
# It exists as a safety net for edge cases (e.g., replication lag, future regressions).
_POLL_MAX_ATTEMPTS = 3
_POLL_SLEEP_SECONDS = 1


@celery_app.task(
    name="notification.send_push",
    bind=True,
    acks_late=True,
    max_retries=settings.NOTIFICATION_MAX_RETRIES,
    autoretry_for=(
        ConnectionError, TimeoutError, Provider5xxError, RateLimitError, ProviderFailedError, SoftTimeLimitExceeded,
        requests.exceptions.RequestException
    ),
    retry_backoff=30,
    retry_backoff_max=1800,
    retry_jitter=True,
)
def send_push_notification(
    self,
    notification_id: str,
    tokens: list,
    template_id: str,
    payload: dict,
    subject: str = None,
    request_id: str = None,
    user_id: str = None,
):
    """Send a PUSH notification batch via Firebase Cloud Messaging (FCM)."""
    log_extra = {
        "notification_id": notification_id,
        "channel": "PUSH",
        "token_count": len(tokens),
        "request_id": request_id,
        "celery_task_id": self.request.id,
    }

    logger.info("Push task started", extra={**log_extra, "event": "task_started"})

    # ── DB visibility guard ──────────────────────────────────────────────────
    # Poll until the NotificationHistory record is visible, or give up and
    # raise so the task is marked FAILED (not silently skipped).
    record = NotificationService.wait_for_record(
        db_session_factory=get_db_session,
        notification_id=UUID(notification_id),
        max_attempts=_POLL_MAX_ATTEMPTS,
        sleep_seconds=_POLL_SLEEP_SECONDS,
    )

    if record is None:
        logger.error(
            "Push task aborted: NotificationHistory record not found after polling",
            extra={**log_extra, "event": "task_record_not_found_giving_up"},
        )
        raise RuntimeError(
            f"NotificationHistory {notification_id} not visible after "
            f"{_POLL_MAX_ATTEMPTS} attempt(s). Aborting task."
        )

    logger.info(
        "Push task: DB record found",
        extra={**log_extra, "event": "task_db_record_found", "status": record.status},
    )

    # ── Idempotency check ────────────────────────────────────────────────────
    if record.status == NotificationStatus.SENT.value:
        logger.info(
            "Push task: already sent, skipping",
            extra={**log_extra, "event": "task_skipped_already_sent"},
        )
        return {"status": "skipped", "reason": "already_sent"}

    # ── Mark PROCESSING ──────────────────────────────────────────────────────
    with get_db_session() as db:
        NotificationService.mark_processing(db, UUID(notification_id))

    logger.info("Push task: marked PROCESSING", extra={**log_extra, "event": "task_processing"})

    # ── Send ─────────────────────────────────────────────────────────────────
    try:
        channel = PushChannel(
            notification_id=notification_id,
            tokens=tokens,
            template_id=template_id,
            payload=payload,
            subject=subject,
            user_id=user_id,
        )
        result = channel.send()

        with get_db_session() as db:
            NotificationService.mark_sent(
                db, UUID(notification_id), provider_response=result
            )

        logger.info(
            "Push task completed successfully",
            extra={**log_extra, "event": "task_completed", "status": "SENT"},
        )
        return result

    except ValueError as val_err:
        with get_db_session() as db:
            NotificationService.mark_failed(
                db, UUID(notification_id),
                error_message=str(val_err),
                retry_count=self.request.retries,
            )
        logger.error(
            f"Push task failed: validation error — {val_err}",
            extra={**log_extra, "event": "task_failed", "status": "FAILED"},
        )
        return {"status": "failed", "reason": "validation_error", "message": str(val_err)}

    except (
        ConnectionError, TimeoutError, Provider5xxError, RateLimitError, ProviderFailedError, SoftTimeLimitExceeded,
        requests.exceptions.RequestException
    ) as exc:
        # Mark as failed in DB to update error message and retry count.
        # Celery autoretry_for will handle the actual retry logic and backoff.
        with get_db_session() as db:
            NotificationService.mark_failed(
                db, UUID(notification_id),
                error_message=f"Retryable error: {exc}",
                retry_count=self.request.retries,
            )

        logger.warning(
            f"Push task failed (retryable): {exc}. Celery will autoretry. "
            f"(Attempt {self.request.retries + 1}/{self.max_retries})",
            extra={**log_extra, "event": "task_failed_retryable", "retry_count": self.request.retries + 1},
        )
        raise exc

    except Exception as exc:
        with get_db_session() as db:
            NotificationService.mark_failed(
                db, UUID(notification_id),
                error_message=f"Unexpected error: {exc}",
                retry_count=self.request.retries,
            )

        logger.error(
            f"Push task failed (unexpected): {exc}",
            extra={**log_extra, "event": "task_failed", "status": "FAILED"},
        )
        raise
