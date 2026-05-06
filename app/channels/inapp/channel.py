"""
InApp Channel
=============
In-app notification channel. Currently DB-only: the notification_history
record itself IS the in-app notification.

Phase 2: Add WebSocket push or FCM for real-time delivery.
"""

from channels.base import BaseChannel


class InAppChannel(BaseChannel):
    """
    In-App notification channel.
    Currently stores to DB only (via notification_history).
    The frontend polls or queries the notifications endpoint.
    """

    channel_name = "inapp"

    def resolve_template(self) -> str:
        """
        No template rendering needed for DB-only in-app notifications.
        The payload itself contains the notification data.
        """
        return ""

    def send(self) -> dict:
        """
        For in-app, the DB record IS the notification.
        Just mark as sent — the record was already created by the dispatcher.

        Phase 2: Add WebSocket push / Firebase Cloud Messaging here.
        """
        self.logger.info(
            "InApp notification stored (DB-only)",
            extra={
                "notification_id": self.notification_id,
                "channel": "INAPP",
                "user_id": self.payload.get("user_id"),
            },
        )
        return {"success": True, "provider": "db_only"}
