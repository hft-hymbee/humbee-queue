"""
Notification API DTOs
=====================
Request/Response models for the notification API endpoints.
"""

from typing import List, Optional, Union

from pydantic import BaseModel, validator

from domain.enums import NotificationChannel


# ─── Request DTOs ───────────────────────────────────────────────


class SendNotificationDTO(BaseModel):
    """Request body for POST /notification/send"""

    event_type: str
    user_id: Optional[str] = None
    channels: Union[NotificationChannel, List[NotificationChannel]]
    template_id: str
    recipients: Union[str, List[str]]
    subject: Optional[str] = None
    payload: dict = {}
    request_id: Optional[str] = None

    @validator("channels", pre=True)
    def normalize_channels(cls, v):
        """Accept single channel or list of channels."""
        if isinstance(v, list):
            return [v[0]] if v else v
        return [v]

    @validator("recipients", pre=True)
    def normalize_recipients(cls, v):
        """Accept single string or list of strings."""
        if isinstance(v, str):
            return [v]
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "ORDER_PLACED",
                "user_id": "user_123",
                "channels": ["SMS"],
                "template_id": "1234432112344321",
                "recipients": ["8052484213"],
                "subject": "",
                "payload": {
                    "order_id": "ORD-001",
                    "humbee_po_number": "PO-12345",
                    "buyer_name": "ABC Corp",
                },
                "request_id": "req_abc123",
            }
        }


# ─── Response DTOs ──────────────────────────────────────────────


class NotificationResult(BaseModel):
    """Single notification dispatch result."""

    notification_id: str
    channel: str
    status: str
    skipped: Optional[bool] = False


class SendNotificationResponse(BaseModel):
    """Response for POST /notification/send"""

    success: bool
    message: str
    notifications: List[NotificationResult]


class NotificationStatusResponse(BaseModel):
    """Response for GET /notification/{id}"""

    id: str
    event_type: str
    channel: str
    recipient: str
    status: str
    template_id: Optional[str]
    subject: Optional[str]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: str
    sent_at: Optional[str]
    failed_at: Optional[str]

    class Config:
        from_attributes = True


