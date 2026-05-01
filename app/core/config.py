"""
Application Configuration
=========================
Central config using pydantic-settings. Values are loaded from the
SecretsManager (secrets.json locally, K8s env vars in prod).

Usage:
    from core.config import settings
    if settings.is_test_mode:
        ...
"""

import os
from typing import Optional

from core.secrets import secrets_manager


class Settings:
    """Application settings populated from secrets manager."""

    def __init__(self):
        self._load()

    def _load(self):
        # --- Environment ---
        self.ENV: str = os.getenv("ENV", "LOCAL")

        # --- Application Mode ---
        self.APPLICATION_MODE: str = self._get("app", "application_mode", default="TEST")
        self.TEST_EMAIL: Optional[str] = self._get("app", "test_email", default=None)
        self.TEST_PHONE: Optional[str] = self._get("app", "test_phone", default=None)

        # --- SMTP ---
        self.SMTP_SERVER: str = self._get("smtp", "server", default="")
        self.SMTP_PORT: int = int(self._get("smtp", "port", default="587"))
        self.SMTP_USERNAME: str = self._get("smtp", "username", default="")
        self.SMTP_PASSWORD: str = self._get("smtp", "password", default="")
        self.SMTP_FROM_EMAIL: str = self._get("smtp", "from_email", default="")

        # --- Database ---
        self.DATABASE_URL: str = self._get("database", "url", default="")

        # --- Redis ---
        self.REDIS_URL: str = self._get("redis", "url", default="")

        # --- SMS ---
        self.SMS_API_URL: str = self._get("sms", "api_url", default="")
        self.SMS_API_KEY: str = self._get("sms", "api_key", default="")
        self.SMS_ENTITY_ID: str = self._get("sms", "entity_id", default="")
        self.SMS_SIGNATURE: str = self._get("sms", "signature", default="")
        self.SMS_MSG_TYPE: str = self._get("sms", "msg_type", default="")
        self.SMS_USERNAME: str = self._get("sms", "username", default="")

        # --- WhatsApp ---
        self.WHATSAPP_API_URL: str = self._get("whatsapp", "api_url", default="")
        self.WHATSAPP_API_KEY: str = self._get("whatsapp", "api_key", default="")
        self.WHATSAPP_SENDER_ID: str = self._get("whatsapp", "sender_id", default="")
        self.WHATSAPP_MEDIA_UPLOAD_URL: str = self._get("whatsapp", "media_upload_url", default="")

        # --- AWS / S3 ---
        self.AWS_ACCESS_KEY_ID: str = self._get("aws", "access_key_id", default="")
        self.AWS_SECRET_ACCESS_KEY: str = self._get("aws", "secret_access_key", default="")
        self.AWS_REGION: str = self._get("aws", "region", default="ap-south-1")

    def _get(self, group: str, key: str, default=None):
        """Get a secret value, returning default if not found."""
        try:
            return secrets_manager.get_secret(group, key)
        except (KeyError, FileNotFoundError):
            if default is not None:
                return default
            raise

    @property
    def is_test_mode(self) -> bool:
        """Check if the application is in test mode."""
        return self.APPLICATION_MODE == "TEST"

    def get_recipient(self, channel: str, real_recipient: str) -> str:
        """
        In TEST mode, override recipient with test address.
        In PROD mode, return the real recipient.
        """
        if not self.is_test_mode:
            return real_recipient

        channel_upper = channel.upper()
        if channel_upper == "EMAIL" and self.TEST_EMAIL:
            return self.TEST_EMAIL
        if channel_upper in ("SMS", "WHATSAPP") and self.TEST_PHONE:
            return self.TEST_PHONE

        return real_recipient


# Singleton instance
settings = Settings()