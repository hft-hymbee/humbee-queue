"""
Push Channel (FCM)
==================
Sends Firebase Cloud Messaging multicast push notifications.
Writes per-token delivery records to push_delivery_attempts after each send.

Payload contract (fields read from payload dict):
  {
    "title":     "Your order is placed",   ← required
    "body":      "Order #INV-001 ready",   ← required
    "image_url": "https://cdn.example/img.png",  ← optional
    "data":      {"order_id": "123"},      ← optional custom data dict (string values)
    "device_metadata": [                   ← optional, parallel list to tokens
      {"device_id": "uuid", "platform": "ANDROID"},
      {"device_id": "uuid", "platform": "IOS"},
      {},                                  ← use empty dict when metadata is unavailable for a token
      ...
    ]
  }

Test mode behaviour:
  - If settings.TEST_FCM_TOKEN is set: all tokens are replaced with [TEST_FCM_TOKEN].
  - If settings.TEST_FCM_TOKEN is NOT set in TEST mode: send() returns early (skipped).
"""

from uuid import UUID

from firebase_admin import messaging

from channels.base import BaseChannel
from core.config import settings
from core.database import get_db_session
from core.exceptions import ProviderFailedError
from core.firebase_app import get_firebase_app
from services.push_delivery_service import PushDeliveryService


class PushChannel(BaseChannel):
    """
    FCM push notification channel.

    Uses firebase_admin.messaging.send_each_for_multicast() for batches of ≤500 tokens.
    After each send, writes one push_delivery_attempts row per token for observability.
    """

    channel_name = "push"

    def __init__(
        self,
        notification_id: str,
        tokens: list,
        template_id: str,
        payload: dict,
        subject: str = None,
        user_id: str = None,
    ):
        # Call BaseChannel with a placeholder recipient string.
        # BaseChannel.recipient is not used for PUSH — tokens are the real recipients.
        super().__init__(
            notification_id=notification_id,
            recipient="PUSH_MULTICAST",
            template_id=template_id,
            payload=payload,
            subject=subject,
        )

        # Apply test-mode token override via settings
        # get_recipient("push", tokens) returns:
        #   - [TEST_FCM_TOKEN] in TEST mode if configured
        #   - None in TEST mode if TEST_FCM_TOKEN is not configured (skip sending)
        #   - original tokens list in PROD mode
        resolved = settings.get_recipient("push", tokens)
        self.tokens = resolved   # list[str] or None
        self.user_id = user_id

    def resolve_template(self) -> str:
        """No DB-stored template for PUSH — title/body come directly from payload."""
        return ""

    def send(self) -> dict:
        """
        Build FCM MulticastMessage and send to all tokens in this batch.

        Test-mode skip:
            If tokens resolved to None (TEST mode, no test token configured),
            the send is skipped and a 'skipped' result is returned without
            touching Firebase or writing delivery attempt rows.

        Partial failures:
            If some tokens fail, the batch is still marked SENT (partial success).
            Failed token details are stored in push_delivery_attempts for observability.

        All-fail:
            If ALL tokens fail, ProviderFailedError is raised → task retries.
            New push_delivery_attempts rows are inserted on each retry (audit trail).

        Returns:
            dict with success, provider, success_count, failure_count, total_tokens.

        Raises:
            ValueError: If payload is missing required 'title' or 'body'.
            ProviderFailedError: If all tokens fail (triggers Celery retry).
        """
        # --- Test mode: no test token configured → skip silently ---
        if self.tokens is None:
            self.logger.info(
                "TEST mode: no TEST_FCM_TOKEN configured, skipping PUSH send",
                extra={"notification_id": self.notification_id, "channel": "PUSH"},
            )
            return {
                "success": False,
                "provider": "firebase_fcm",
                "skipped": True,
                "reason": "no_test_fcm_token",
            }

        # --- Validate required payload fields ---
        title = self.payload.get("title")
        body  = self.payload.get("body")
        if not title or not body:
            raise ValueError(
                "Payload must contain 'title' and 'body' for PUSH notifications. "
                f"Received keys: {list(self.payload.keys())}"
            )

        self.logger.info(
            f"Sending FCM multicast to {len(self.tokens)} token(s)",
            extra={
                "notification_id": self.notification_id,
                "channel": "PUSH",
                "token_count": len(self.tokens),
            },
        )

        # --- Build FCM objects ---
        notification = messaging.Notification(
            title=title,
            body=body,
            image=self.payload.get("image_url"),
        )
        android_config = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(sound="default"),
        )
        apns_config = messaging.APNSConfig(
            headers={
                'apns-priority': '10', # '10' for immediate delivery
                'apns-push-type': 'alert' # 'background' for silent notifications
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1),
            ),
        )

        # FCM data values must all be strings
        data = {
            str(k): str(v)
            for k, v in self.payload.get("data", {}).items()
        }

        message = messaging.MulticastMessage(
            tokens=self.tokens,
            notification=notification,
            android=android_config,
            apns=apns_config,
            data=data if data else None,
        )

        # --- Initialize Firebase app (no-op if already initialized in this worker) ---
        get_firebase_app()

        # --- Send multicast ---
        batch_response = messaging.send_each_for_multicast(message)

        # --- Write per-token delivery attempt rows ---
        with get_db_session() as db:
            if db:
                PushDeliveryService.bulk_create_from_batch_response(
                    db=db,
                    notification_history_id=UUID(self.notification_id),
                    tokens=self.tokens,
                    batch_response=batch_response,
                    user_id=self.user_id,
                    device_metadata=self.payload.get("device_metadata"),
                )

        # --- Log partial failures ---
        if batch_response.failure_count > 0:
            failed_tokens = [
                {
                    "token": self.tokens[i],
                    "error": (
                        response.exception.code
                        if hasattr(response.exception, "code")
                        else str(response.exception)
                    ),
                }
                for i, response in enumerate(batch_response.responses)
                if not response.success
            ]
            self.logger.warning(
                f"FCM partial failure: {batch_response.failure_count}/{len(self.tokens)} token(s) failed",
                extra={
                    "notification_id": self.notification_id,
                    "failed_tokens": failed_tokens,
                },
            )

        # --- Raise if all tokens failed (triggers Celery retry) ---
        if batch_response.success_count == 0:
            raise ProviderFailedError(
                f"All {len(self.tokens)} FCM token(s) failed. "
                "See push_delivery_attempts for per-token error codes."
            )

        return {
            "success": True,
            "provider": "firebase_fcm",
            "success_count": batch_response.success_count,
            "failure_count": batch_response.failure_count,
            "total_tokens": len(self.tokens),
        }
