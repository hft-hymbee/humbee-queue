"""
SMS Channel
===========
Resolves SMS templates, substitutes variables, and sends via Telspiel API.
"""
import requests
from channels.base import BaseChannel
from core.config import settings
from core.database import get_db_session
from core.exceptions import Provider5xxError, RateLimitError
from services.template_service import TemplateService


class SMSChannel(BaseChannel):
    """
    SMS notification channel using Telspiel provider.
    Template content is stored locally; variables substituted at runtime.
    """

    channel_name = "sms"

    def resolve_template(self) -> str:
        """
        Load SMS template content and substitute variables from payload.
        Returns the final SMS message text.
        """
        with get_db_session() as db:
            if not db:
                raise ValueError("Database session unavailable for SMS template resolution")
                
            template = TemplateService.get_sms_template(db, self.template_id)
            if not template:
                raise ValueError(f"No SMS template found for template_id: {self.template_id}")

            payload_keys_count = len(self.payload.keys())
            if payload_keys_count < template.variables_count:
                error_msg = f"Variable count mismatch for template {self.template_id}. Required at least {template.variables_count}, got {payload_keys_count}."
                self.logger.error(error_msg, extra={"notification_id": self.notification_id})
                raise ValueError(error_msg)

            message_type = template.message_type
            content = template.content
            
            try:
                message = content.format(**self.payload)
            except KeyError as e:
                raise ValueError(
                    f"Missing variable {e} in payload for SMS template '{self.template_id}'"
                )

        self.logger.info(   
            "SMS template resolved",
            extra={
                "notification_id": self.notification_id,
                "template_id": self.template_id,
                "channel": "SMS",
            },
        )
        return message, message_type

    def send(self) -> dict:
        """
        Resolve template and send SMS via Telspiel.

        Returns:
            dict with provider response
        """
        message, message_type = self.resolve_template()

        self.logger.info(
            f"Sending SMS to {self.recipient}",
            extra={
                "notification_id": self.notification_id,
                "channel": "SMS",
                "recipient": self.recipient,
            },
        )
        
        params = {
            "username": settings.SMS_USERNAME,
            "apikey": settings.SMS_API_KEY,
            "signature": settings.SMS_SIGNATURE,
            "msgtype": message_type if message_type else settings.SMS_MSG_TYPE,
            "entityid": settings.SMS_ENTITY_ID,
            "dest": self.recipient,
            "msgtxt": message,
            "templateid": self.template_id,
        }

        response = requests.get(
            settings.SMS_API_URL,
            params=params
        )
        
        if response.status_code == 429:
            raise RateLimitError(f"SMS Rate Limit Exceeded: {response.text}")
        elif response.status_code >= 500:
            raise Provider5xxError(f"SMS Provider Server Error ({response.status_code}): {response.text}")
            
        response.raise_for_status()
        return {"success": True, "provider": "telspiel", "response": response.json()}
