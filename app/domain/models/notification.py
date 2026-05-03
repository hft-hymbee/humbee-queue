"""
Notification History ORM Model
===============================
SQLAlchemy model for the notification_history table.
Tracks every notification sent through the engine.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base
from core.config import settings
from domain.enums import NotificationStatus


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(100), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    channel = Column(String(20), nullable=False, index=True)
    template_id = Column(String(200), nullable=True)
    recipient = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=True)
    payload = Column(JSONB, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default=NotificationStatus.QUEUED.value,
        index=True,
    )
    provider_response = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=lambda: settings.NOTIFICATION_MAX_RETRIES)
    celery_task_id = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Composite index for common query pattern
    __table_args__ = (
        Index("idx_nh_user_channel_status", "user_id", "channel", "status"),
    )

    def __repr__(self):
        return (
            f"<NotificationHistory(id={self.id}, channel={self.channel}, "
            f"status={self.status}, recipient={self.recipient})>"
        )
