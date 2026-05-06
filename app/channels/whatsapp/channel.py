"""
WhatsApp Channel
================
Resolves WhatsApp template IDs and sends via WhatsApp aggregator API.

NOTE: The actual aggregator API integration (send() method body) is a TODO.
      The template resolution and all surrounding logic is implemented.
"""
import requests
from channels.base import BaseChannel
from channels.whatsapp.templates import WA_TEMPLATES
from services.s3_service import S3Service
from core.config import settings


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp notification channel.
    Template ID is resolved locally; the provider manages template content.
    Variables are passed to the provider API at send time.
    """

    channel_name = "whatsapp"

    def resolve_template(self) -> str:
        """
        Resolve the WhatsApp provider template ID from internal template_id.
        Returns the provider-side template ID string.
        """
        wa_template_config = WA_TEMPLATES.get(self.template_id)
        if not wa_template_config:
            raise ValueError(
                f"No WhatsApp template found for template_id: {self.template_id}"
            )

        provider_template_id = wa_template_config["provider_template_id"]

        self.logger.info(
            f"WhatsApp template resolved: {self.template_id} → {provider_template_id}",
            extra={
                "notification_id": self.notification_id,
                "template_id": self.template_id,
                "channel": "WHATSAPP",
            },
        )
        return provider_template_id

    def _upload_media_to_provider(self, file_data: dict) -> str:
        """Upload raw file bytes to the WhatsApp aggregator and return the public URL."""
        if not settings.WHATSAPP_MEDIA_UPLOAD_URL:
            self.logger.warning("WHATSAPP_MEDIA_UPLOAD_URL not configured. Skipping attachment upload.")
            return ""

        upload_resp = requests.post(
            settings.WHATSAPP_MEDIA_UPLOAD_URL,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_API_KEY}"},
            files={"file": (file_data["filename"], file_data["bytes"])}
        )
        upload_resp.raise_for_status()

        # Extract the public URL from provider response (adjust key based on provider docs)
        public_url = upload_resp.json().get("media_url") or upload_resp.json().get("url")
        return public_url or ""

    def _process_media_attachments(self, wa_template_config: dict) -> list:
        """Download attachments from S3 and upload to provider."""
        media_urls = []
        if not wa_template_config.get("has_attachment"):
            return media_urls

        payload_keys = wa_template_config.get("attachment_payload_keys", [])
        for key in payload_keys:
            s3_url = self.payload.get(key)
            if s3_url:
                file_data = S3Service.download_file(s3_url)
                public_url = self._upload_media_to_provider(file_data)
                if public_url:
                    media_urls.append(public_url)

        return media_urls

    def send(self) -> dict:
        """
        Resolve template ID, process attachments, and send WhatsApp message via aggregator.

        Returns:
            dict with provider response
        """
        wa_template_id = self.resolve_template()
        wa_template_config = WA_TEMPLATES.get(self.template_id)
        
        variables = dict(self.payload)
        
        # Handle Attachments via S3 -> Aggregator Upload
        media_urls = self._process_media_attachments(wa_template_config)
        
        # Inject media URLs into payload variables if they exist
        if media_urls:
            variables["media_urls"] = media_urls

        self.logger.info(
            f"Sending WhatsApp via aggregator API",
            extra={
                "notification_id": self.notification_id,
                "channel": "WHATSAPP",
                "template_id": self.template_id,
                "recipient": self.recipient,
                "has_media": bool(media_urls)
            },
        )
        
        response = requests.post(
            settings.WHATSAPP_API_URL,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_API_KEY}"},
            json={
                "phone": self.recipient,
                "template_id": wa_template_id,
                "variables": variables,
                "sender_id": settings.WHATSAPP_SENDER_ID,
            },
        )
        response.raise_for_status()
        return {"success": True, "provider": "whatsapp_aggregator", "response": response.json()}
