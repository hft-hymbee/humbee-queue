"""
Application Configuration
=========================
Central config using pydantic-settings. Values are loaded from the
SecretsManager (secrets.json locally, AWS Secrets Manager in QA/PROD).

Usage:
    from core.config import settings
    if settings.is_test_mode:
        ...
"""

import os
from typing import Optional, Union

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
        self.TEST_FCM_TOKEN: Optional[str] = self._get("app", "test_fcm_token", default=None)

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
        self.TEMPLATE_CACHE_TTL: int = int(self._get("redis", "template_cache_ttl", default="86400")) # 24 * 60 * 60 seconds

        # --- SMS ---
        self.SMS_API_URL: str = self._get("sms", "api_url", default="")
        self.SMS_API_KEY: str = self._get("sms", "api_key", default="")
        self.SMS_ENTITY_ID: str = self._get("sms", "entity_id", default="")
        self.SMS_SIGNATURE: str = self._get("sms", "signature", default="")
        self.SMS_MSG_TYPE: str = self._get("sms", "msg_type", default="")
        self.SMS_USERNAME: str = self._get("sms", "username", default="")

        # --- WhatsApp ---
        self.WHATSAPP_API_URL: str = self._get("whatsapp", "api_url", default="")
        self.WHATSAPP_AUTHENTICATION_TYPE: str = self._get("whatsapp", "authentication_type", default="")
        self.WHATSAPP_LONG_TERM_TOKEN: str = self._get("whatsapp", "long_term_token", default="")
        self.WHATSAPP_JOURNEY_ID: str = self._get("whatsapp", "journey_id", default="")
        self.WHATSAPP_ADMIN_PHONE_NO: str = self._get("whatsapp", "admin_phone_no", default="")

        # --- AWS ---
        self.AWS_REGION: str = self._get("aws", "region", default="ap-south-1")
        self.AWS_ACCESS_KEY_ID: Optional[str] = self._get("aws", "access_key_id", default=None)
        self.AWS_SECRET_ACCESS_KEY: Optional[str] = self._get("aws", "secret_access_key", default=None)

        # --- Notifications ---
        self.NOTIFICATION_MAX_RETRIES: int = int(self._get("notifications", "max_retries", default="3"))

        # --- Firebase / FCM ---
        self.FCM_SERVICE_ACCOUNT_JSON: dict = self._get("firebase", "service_account_json", default={})

        # --- API Keys ---
        self.SHARED_API_KEY: str = self._get("api_keys", "shared_key", default="")
        self.ADMIN_KEYS: dict = self._get("api_keys", "admin_keys", default={})
        self.ADMIN_KEY_VALUES: set = set(self.ADMIN_KEYS.values())
        self.ADMIN_KEY_LOOKUP: dict = {v: k for k, v in self.ADMIN_KEYS.items()}

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

    def get_recipient(
        self, channel: str, real_recipient: Union[str, list[str]]
    ) -> Union[str, list[str], None]:
        """
        In TEST mode, override recipient with the configured test address.
        In PROD mode, return the real recipient unchanged.

        For PUSH channel:
          - real_recipient is a list[str] of FCM tokens
          - Returns [TEST_FCM_TOKEN] in TEST mode if a test token is configured.
          - Returns None in TEST mode if no TEST_FCM_TOKEN is set (skip sending).
          - Returns the original list in PROD mode.
        For all other channels:
          - real_recipient is a str
          - Returns the test address in TEST mode, or the original str in PROD.
        """
        if not self.is_test_mode:
            return real_recipient

        channel_upper = channel.upper()
        if channel_upper == "EMAIL" and self.TEST_EMAIL:
            return self.TEST_EMAIL
        if channel_upper in ("SMS", "WHATSAPP") and self.TEST_PHONE:
            return self.TEST_PHONE
        if channel_upper == "PUSH":
            if self.TEST_FCM_TOKEN:
                return [self.TEST_FCM_TOKEN]
            # No test token configured — caller should skip sending
            return None

        return real_recipient


# Singleton instance
settings = Settings()