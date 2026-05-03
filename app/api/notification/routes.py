"""
Notification API Routes
=======================
FastAPI endpoints for sending and tracking notifications.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.notification.dtos import (
    SendNotificationDTO,
    SendNotificationResponse,
    NotificationResult,
    NotificationStatusResponse,
)
from core.database import get_db
from core.logging import get_logger
from services.dispatcher import NotificationDispatcher
from services.notification_service import NotificationService

logger = get_logger("api.notification")

notification_router = APIRouter(prefix="/notification", tags=["notification"])


@notification_router.post("/send", response_model=SendNotificationResponse)
def send_notification(
    dto: SendNotificationDTO,
    db: Session = Depends(get_db),
):
    """
    Send notification(s) across specified channels.

    Creates a notification_history record per (channel × recipient) and
    dispatches each as a separate Celery task to the appropriate queue.
    """
    logger.info(
        "Notification send request received",
        extra={
            "event_type": dto.event_type,
            "channels": [c.value for c in dto.channels],
            "recipients_count": len(dto.recipients),
            "request_id": dto.request_id,
            "user_id": dto.user_id,
        },
    )

    try:
        dispatcher = NotificationDispatcher(db=db)
        results = dispatcher.dispatch(
            event_type=dto.event_type,
            channels=dto.channels,
            recipients=dto.recipients,
            template_id=dto.template_id,
            payload=dto.payload,
            user_id=dto.user_id,
            subject=dto.subject,
            request_id=dto.request_id,
        )

        notification_results = [
            NotificationResult(**r) for r in results
        ]

        return SendNotificationResponse(
            success=True,
            message=f"{len(results)} notification(s) queued successfully",
            notifications=notification_results,
        )

    except Exception as e:
        logger.error(f"Failed to dispatch notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch notification: {str(e)}",
        )


@notification_router.get("/{notification_id}", response_model=NotificationStatusResponse)
def get_notification_status(
    notification_id: str,
    db: Session = Depends(get_db),
):
    """Get the current status of a notification by ID."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        record = NotificationService.get_by_id(db, UUID(notification_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")

    if not record:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationStatusResponse(
        id=str(record.id),
        event_type=record.event_type,
        channel=record.channel,
        recipient=record.recipient,
        status=record.status,
        template_id=record.template_id,
        subject=record.subject,
        error_message=record.error_message,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        created_at=record.created_at.isoformat() if record.created_at else None,
        sent_at=record.sent_at.isoformat() if record.sent_at else None,
        failed_at=record.failed_at.isoformat() if record.failed_at else None,
    )


@notification_router.get("/user/{user_id}")
def get_user_notifications(
    user_id: str,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get all notifications for a user, optionally filtered by channel and status."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    records = NotificationService.get_by_user_id(
        db, user_id, channel=channel, status=status, limit=limit
    )

    return {
        "user_id": user_id,
        "count": len(records),
        "notifications": [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "channel": r.channel,
                "recipient": r.recipient,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
