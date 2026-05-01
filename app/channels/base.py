"""
Base Channel
============
Abstract base class for all notification channels.
Every channel must implement resolve_template() and send().
"""

from abc import ABC, abstractmethod
from typing import Optional

from core.config import settings
from core.logging import get_logger


class BaseChannel(ABC):
    """
    Abstract base for notification channels.

    Each channel subclass must:
    1. Set `channel_name` class attribute
    2. Implement `resolve_template()` — render content for this channel
    3. Implement `send()` — deliver via the channel's provider

    The base class handles:
    - Test mode recipient override
    - Logger setup with channel name
    """

    channel_name: str = ""  # Override in subclass

    def __init__(
        self,
        notification_id: str,
        recipient: str,
        template_id: str,
        payload: dict,
        subject: Optional[str] = None,
    ):
        self.notification_id = notification_id
        self.template_id = template_id
        self.payload = payload
        self.subject = subject
        self.logger = get_logger(f"channel.{self.channel_name}")

        # Apply test mode recipient override
        self.original_recipient = recipient
        self.recipient = settings.get_recipient(self.channel_name, recipient)

        if self.recipient != self.original_recipient:
            self.logger.info(
                f"Test mode: recipient overridden from {self.original_recipient} to {self.recipient}",
                extra={
                    "notification_id": self.notification_id,
                    "channel": self.channel_name.upper(),
                    "application_mode": settings.APPLICATION_MODE,
                },
            )

    @abstractmethod
    def resolve_template(self) -> str:
        """
        Resolve and render the template content for this channel.
        Returns the rendered content (HTML for email, text for SMS, template ID for WhatsApp).
        """
        pass

    @abstractmethod
    def send(self) -> dict:
        """
        Send the notification via this channel's provider.
        Returns a dict with at least: {"success": bool, "provider": str}
        May include additional provider-specific response data.
        """
        pass
