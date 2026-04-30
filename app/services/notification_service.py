"""
Notification Service
====================
DB CRUD operations for notification_history records.
Used by both the API layer (to create records) and Celery tasks (to update status).

Usage:
    from services.notification_service import NotificationService

    # Create a record
    NotificationService.create(db, id=..., event_type=..., ...)

    # Update status
    NotificationService.mark_sent(db, notification_id, provider_response={...})
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from core.logging import get_logger
from domain.enums import NotificationStatus
from domain.models import NotificationHistory

logger = get_logger("service.notification")


class NotificationService:
    """CRUD operations for notification history records."""

    @staticmethod
    def create(
        db: Session,
        id: UUID,
        event_type: str,
        channel: str,
        recipient: str,
        template_id: str = None,
        user_id: str = None,
        subject: str = None,
        payload: dict = None,
        request_id: str = None,
        celery_task_id: str = None,
    ) -> NotificationHistory:
        """Create a new notification record with status QUEUED."""
        record = NotificationHistory(
            id=id,
            request_id=request_id,
            event_type=event_type,
            user_id=user_id,
            channel=channel,
            template_id=template_id,
            recipient=recipient,
            subject=subject,
            payload=payload,
            status=NotificationStatus.QUEUED.value,
            celery_task_id=celery_task_id,
        )
        db.add(record)
        db.flush()  # Get the ID without committing

        logger.info(
            "Notification record created",
            extra={
                "notification_id": str(id),
                "channel": channel,
                "event_type": event_type,
                "user_id": user_id,
                "status": NotificationStatus.QUEUED.value,
                "request_id": request_id,
            },
        )
        return record

    @staticmethod
    def get_by_id(db: Session, notification_id: UUID) -> Optional[NotificationHistory]:
        """Get a notification record by ID."""
        return db.query(NotificationHistory).filter(
            NotificationHistory.id == notification_id
        ).first()

    @staticmethod
    def update_status(
        db: Session,
        notification_id: UUID,
        status: NotificationStatus,
        provider_response: dict = None,
        error_message: str = None,
        retry_count: int = None,
    ) -> Optional[NotificationHistory]:
        """Update the status of a notification record."""
        record = NotificationService.get_by_id(db, notification_id)
        if not record:
            logger.error(
                "Notification record not found for status update",
                extra={"notification_id": str(notification_id), "status": status.value},
            )
            return None

        now = datetime.now(timezone.utc)
        record.status = status.value
        record.updated_at = now

        if provider_response is not None:
            record.provider_response = provider_response
        if error_message is not None:
            record.error_message = error_message
        if retry_count is not None:
            record.retry_count = retry_count

        if status == NotificationStatus.SENT:
            record.sent_at = now
        elif status == NotificationStatus.DELIVERED:
            record.sent_at = record.sent_at or now
        elif status == NotificationStatus.FAILED:
            record.failed_at = now

        db.flush()

        logger.info(
            f"Notification status updated to {status.value}",
            extra={
                "notification_id": str(notification_id),
                "status": status.value,
                "channel": record.channel,
                "retry_count": record.retry_count,
            },
        )
        return record

    @staticmethod
    def mark_processing(db: Session, notification_id: UUID) -> Optional[NotificationHistory]:
        """Mark notification as PROCESSING (worker picked it up)."""
        return NotificationService.update_status(
            db, notification_id, NotificationStatus.PROCESSING
        )

    @staticmethod
    def mark_sent(
        db: Session,
        notification_id: UUID,
        provider_response: dict = None,
    ) -> Optional[NotificationHistory]:
        """Mark notification as SENT with optional provider response."""
        return NotificationService.update_status(
            db, notification_id, NotificationStatus.SENT,
            provider_response=provider_response,
        )

    @staticmethod
    def mark_failed(
        db: Session,
        notification_id: UUID,
        error_message: str,
        retry_count: int = 0,
        provider_response: dict = None,
    ) -> Optional[NotificationHistory]:
        """Mark notification as FAILED with error details."""
        return NotificationService.update_status(
            db, notification_id, NotificationStatus.FAILED,
            provider_response=provider_response,
            error_message=error_message,
            retry_count=retry_count,
        )

    @staticmethod
    def get_by_request_id(db: Session, request_id: str) -> List[NotificationHistory]:
        """Get all notifications for a given request_id (idempotency check)."""
        return db.query(NotificationHistory).filter(
            NotificationHistory.request_id == request_id
        ).all()

    @staticmethod
    def get_by_user_id(
        db: Session,
        user_id: str,
        channel: str = None,
        status: str = None,
        limit: int = 50,
    ) -> List[NotificationHistory]:
        """Get notifications for a user, optionally filtered by channel and status."""
        query = db.query(NotificationHistory).filter(
            NotificationHistory.user_id == user_id
        )
        if channel:
            query = query.filter(NotificationHistory.channel == channel)
        if status:
            query = query.filter(NotificationHistory.status == status)

        return query.order_by(NotificationHistory.created_at.desc()).limit(limit).all()
