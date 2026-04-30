from enum import Enum


class NotificationChannel(str, Enum):
    """Supported notification delivery channels."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    INAPP = "INAPP"


class NotificationStatus(str, Enum):
    """Lifecycle status of a notification."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
