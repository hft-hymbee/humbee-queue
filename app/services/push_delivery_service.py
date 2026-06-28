"""
Push Delivery Service
=====================
Bulk-inserts per-token delivery attempt records into push_delivery_attempts
after an FCM multicast BatchResponse is received.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.logging import get_logger
from domain.models.push_delivery import PushDeliveryAttempt

logger = get_logger(__name__)


class PushDeliveryService:
    """CRUD operations for push_delivery_attempts records."""

    @staticmethod
    def bulk_create_from_batch_response(
        db: Session,
        notification_history_id: UUID,
        tokens: list,
        batch_response,
        user_id: str = None,
        device_metadata: list = None,
    ) -> None:
        """
        Insert one PushDeliveryAttempt row per token based on FCM BatchResponse.

        Each retry call will insert NEW rows (intentional audit trail).
        Old rows from previous attempts are preserved.

        Args:
            db:                      Active DB session (caller commits).
            notification_history_id: FK to the parent notification_history batch record.
            tokens:                  Ordered list of FCM tokens sent in this batch.
            batch_response:          firebase_admin.messaging.BatchResponse object.
            user_id:                 Optional user ID (same for all tokens in this batch).
            device_metadata:         Optional list of dicts, parallel to tokens.
                                     Each dict may contain: device_id (str), platform (str).
                                     Missing entries default to None.
        """
        now = datetime.now(timezone.utc)
        records = []

        for i, (token, response) in enumerate(zip(tokens, batch_response.responses)):
            meta = (
                device_metadata[i]
                if device_metadata and i < len(device_metadata)
                else None
            ) or {}  # defensive fallback: caller should pass {} for tokens with no metadata


            if response.success:
                status = "SENT"
                provider_message_id = response.message_id
                error_code = None
                sent_at = now
            else:
                status = "FAILED"
                provider_message_id = None
                error_code = (
                    response.exception.code
                    if hasattr(response.exception, "code")
                    else type(response.exception).__name__
                )
                sent_at = None

            records.append(
                PushDeliveryAttempt(
                    id=uuid4(),
                    notification_history_id=notification_history_id,
                    user_id=user_id,
                    fcm_token=token,
                    device_id=meta.get("device_id"),
                    platform=meta.get("platform"),
                    status=status,
                    provider_message_id=provider_message_id,
                    error_code=error_code,
                    sent_at=sent_at,
                    created_at=now,
                )
            )

        # Bulk insert — one round-trip for up to 500 rows
        db.bulk_save_objects(records)
        # Note: caller is responsible for commit (or we commit here for isolation)
        db.commit()

        logger.info(
            "Push delivery attempts saved",
            extra={
                "notification_history_id": str(notification_history_id),
                "total_tokens": len(records),
                "success_count": batch_response.success_count,
                "failure_count": batch_response.failure_count,
            },
        )
