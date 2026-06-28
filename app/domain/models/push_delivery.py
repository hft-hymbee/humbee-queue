"""
Push Delivery Attempt ORM Model
================================
Tracks the per-token outcome of every FCM multicast send.
One row per token, per notification_history batch record.

Linked to notification_history via FK (CASCADE on delete).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class PushDeliveryAttempt(Base):
    __tablename__ = "push_delivery_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK → notification_history (the parent batch record e.g. "PUSH_BATCH_1_OF_3")
    notification_history_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_history.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = Column(String(100), nullable=True)   # passed through from dispatcher
    fcm_token = Column(String(512), nullable=False)  # FCM tokens can be ~150+ chars
    device_id = Column(String(255), nullable=True)   # caller-supplied, optional
    platform = Column(String(20), nullable=True)   # "ANDROID" | "IOS" | "WEB" — optional

    # Outcome fields (populated after FCM BatchResponse)
    status = Column(String(20), nullable=False)  # "SENT" | "FAILED"
    provider_message_id = Column(String(512), nullable=True)   # FCM message_id on success
    error_code = Column(String(100), nullable=True)   # FCM error code on failure

    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_pda_notification_history_id", "notification_history_id"),
        Index("idx_pda_user_id", "user_id"),
        Index("idx_pda_fcm_token", "fcm_token"),
        Index("idx_pda_status", "status"),
    )

    def __repr__(self):
        return (
            f"<PushDeliveryAttempt(id={self.id}, "
            f"token={self.fcm_token[:20]}..., status={self.status})>"
        )
