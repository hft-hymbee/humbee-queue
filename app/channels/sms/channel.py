"""
SMS Channel
===========
Resolves SMS templates, substitutes variables, and sends via Telspiel API.
"""
import requests
from channels.base import BaseChannel
from channels.sms.templates import SMS_TEMPLATES
from core.config import settings


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
        template = SMS_TEMPLATES.get(self.template_id)
        if not template:
            raise ValueError(
                f"No SMS template found for template_id: {self.template_id}"
            )

        try:
            message_type = template.get("message_type", None)
            content = template.get("content", None)
            if content is None:
                raise ValueError(
                    f"No content found for SMS template '{self.template_id}'"
                )
            
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
        response.raise_for_status()
        return {"success": True, "provider": "telspiel", "response": response.json()}
