"""
WhatsApp Channel
================
Validates data against template metadata and sends messages via the Telspiel API.

Request body shapes:

Case A — Text-only template:
{
  "from": "919XXXXXXXXX",
  "to": "919XXXXXXXXX",
  "journeyId": "...",
  "message": {
    "template": {
      "templateId": "template_id_1",
      "parameterValues": {"0": "ABC", "1": "INV-001", "3": "ABC"}
    }
  }
}

Case B — Media template (DOC / IMAGE / VIDEO):
{
  "from": "919XXXXXXXXX",
  "to": "919XXXXXXXXX",
  "journeyId": "...",
  "message": {
    "template": {
      "templateId": "template_id",
      "parameterValues": {"0": "ABC", "1": "INV-001"},
      "media": {
        "type": "DOC",
        "url": "https://...",
        "fileName": "invoice.pdf"
      }
    }
  }
}
"""
import requests
from channels.base import BaseChannel
from core.config import settings
from core.database import get_db_session
from core.exceptions import Provider5xxError, RateLimitError, ProviderFailedError
from services.whatsapp_template_service import WhatsAppTemplateService
from api.templates.whatsapp.dtos import WhatsAppTemplateResponse


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp notification channel using TelSpiel provider.

    Template metadata (variables_map, has_media, media_type) is stored in the DB.
    The actual message content lives on the TelSpiel platform — we only pass the
    template ID + resolved parameter values + optional media details.
    """

    channel_name = "whatsapp"

    def resolve_template(self) -> "WhatsAppTemplateResponse":
        """
        Load WhatsApp template metadata from the database and return it as a
        Pydantic response model.

        Returning a Pydantic model (not the raw ORM object) is intentional: the
        DB session is closed when the `with` block exits, and accessing ORM
        attributes after that raises a DetachedInstanceError. Converting inside
        the session eagerly loads all fields into a plain Python object that is
        safe to use after the session closes.
        """

        with get_db_session() as db:
            if not db:
                self.logger.error(
                    "Database session unavailable for WhatsApp template resolution",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP"},
                )
                raise ValueError("Database session unavailable for WhatsApp template resolution")

            template = WhatsAppTemplateService.get_whatsapp_template(db, self.template_id)
            if not template:
                self.logger.error(
                    f"No WhatsApp template found for template_id: '{self.template_id}'",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP"},
                )
                raise ValueError(f"No WhatsApp template found for template_id: '{self.template_id}'")

            # Materialize template to a Pydantic model to avoid DetachedInstanceError
            # since DB session is closed after this function call
            template_response = WhatsAppTemplateResponse.model_validate(template)

        self.logger.info(
            f"WhatsApp template resolved: '{self.template_id}'",
            extra={
                "notification_id": self.notification_id,
                "template_id": self.template_id,
                "channel": "WHATSAPP",
                "has_media": template_response.has_media,
            },
        )
        return template_response

    def _resolve_variables(self, template) -> dict:
        """
        Translate named payload variables to the positional dict required by TelSpiel.

        template.variables_map: {"buyer_name": ["0", "3"], "invoice_no": ["1"]}
        self.payload:           {"buyer_name": "Acme", "invoice_no": "INV-001"}
        result:                 {"0": "Acme", "1": "INV-001", "3": "Acme"}

        A variable whose value is a list of positions will have its payload value
        written to every one of those positions (fan-out).

        Returns an empty dict if the template has no variables.
        Raises ValueError if a required variable is missing from the payload.
        """
        if template.variables_count == 0:
            return {}

        parameter_values = {}
        for name, positions in template.variables_map.items():
            if name not in self.payload:
                self.logger.error(
                    f"Missing required variable '{name}' for WhatsApp template '{self.template_id}'",
                    extra={
                        "notification_id": self.notification_id,
                        "template_id": self.template_id,
                        "channel": "WHATSAPP",
                        "missing_variable": name,
                        "expected_variables": list(template.variables_map.keys()),
                    },
                )
                raise ValueError(
                    f"Missing required variable '{name}' for WhatsApp template '{self.template_id}'. "
                    f"Expected variables: {list(template.variables_map.keys())}"
                )
            value = self.payload[name]
            for position in positions:
                parameter_values[position] = value

        return parameter_values

    def _resolve_media(self, template) -> dict | None:
        """
        Validate and extract media details from payload["media_payload"].

        Rules:
        - has_media=False + payload has "media_payload" key  → ValueError (text-only template)
        - has_media=True  + payload missing "media_payload"  → ValueError (media required)
        - has_media=True  + media present            → validate url/type/file_name + type match
        - has_media=False + no media in payload      → return None

        Expected payload["media_payload"] shape:
        {
            "url":       "https://...",
            "type":      "DOC" | "IMAGE" | "VIDEO",
            "file_name": "invoice.pdf"
        }

        Returns a dict formatted for TelSpiel's media block, or None.
        """
        client_media = self.payload.get("media_payload")

        if not template.has_media:
            if client_media:
                self.logger.error(
                    f"Template '{self.template_id}' is text-only but media payload was provided",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP"},
                )
                raise ValueError(
                    f"Template '{self.template_id}' is a text-only template but "
                    f"media details were provided in the payload. Remove the 'media_payload' key."
                )
            return None

        # Template requires media
        if not client_media:
            self.logger.error(
                f"Template '{self.template_id}' requires media but 'media_payload' key is missing",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP", "expected_media_type": template.media_type},
            )
            raise ValueError(
                f"Template '{self.template_id}' requires media (type: {template.media_type}) "
                f"but the 'media_payload' key is missing from the payload."
            )

        media_url = client_media.get("url")
        media_type = client_media.get("type")
        media_filename = client_media.get("file_name")

        if not all([media_url, media_type, media_filename]):
            missing = [
                k for k, v in {
                    "url": media_url, "type": media_type, "file_name": media_filename
                }.items() if not v
            ]
            self.logger.error(
                f"Incomplete media payload for template '{self.template_id}': missing fields {missing}",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP", "missing_fields": missing},
            )
            raise ValueError(
                f"Incomplete media payload for template '{self.template_id}'. "
                f"Missing fields: {missing}. Required: 'url', 'type', 'file_name'."
            )

        if media_type != template.media_type:
            self.logger.error(
                f"Media type mismatch for template '{self.template_id}': expected '{template.media_type}', got '{media_type}'",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "WHATSAPP", "expected": template.media_type, "provided": media_type},
            )
            raise ValueError(
                f"Media type mismatch for template '{self.template_id}': "
                f"template expects '{template.media_type}', payload provided '{media_type}'."
            )

        return {
            "type": media_type,
            "url": media_url,
            "fileName": media_filename,
        }

    def _get_template_data(self, template, parameter_values: dict, media: dict | None) -> dict:
        """Build the 'template' sub-object for the TelSpiel request body."""
        template_data = {"templateId": template.template_id}

        if parameter_values:
            template_data["parameterValues"] = parameter_values

        if media:
            template_data["media"] = media

        return template_data

    def _request_body(self, template, parameter_values: dict, media: dict | None) -> dict:
        """Assemble the full TelSpiel POST request body."""
        return {
            "from": f"91{settings.WHATSAPP_ADMIN_PHONE_NO}",
            "to": f"91{self.recipient}",
            "journeyId": settings.WHATSAPP_JOURNEY_ID,
            "message": {
                "template": self._get_template_data(template, parameter_values, media)
            },
        }

    def _get_default_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            settings.WHATSAPP_AUTHENTICATION_TYPE: settings.WHATSAPP_LONG_TERM_TOKEN,
        }

    def send(self) -> dict:
        """
        Resolve template metadata, validate and translate variables + media,
        then send WHATSAPP via TelSpiel.

        Returns:
            dict with provider response
        """
        template = self.resolve_template()
        parameter_values = self._resolve_variables(template)
        media = self._resolve_media(template)

        self.logger.info(
            f"Sending WhatsApp to {self.recipient}",
            extra={
                "notification_id": self.notification_id,
                "channel": "WHATSAPP",
                "recipient": self.recipient,
                "has_media": bool(media),
            },
        )

        response = requests.post(
            url=settings.WHATSAPP_API_URL,
            headers=self._get_default_headers(),
            json=self._request_body(template, parameter_values, media),
        )

        if response.status_code == 429:
            self.logger.error(
                f"WhatsApp Rate Limit Exceeded (HTTP 429)",
                extra={"notification_id": self.notification_id, "channel": "WHATSAPP", "recipient": self.recipient, "response": response.text},
            )
            raise RateLimitError(f"WhatsApp Rate Limit Exceeded: {response.text}")
        elif response.status_code >= 500:
            self.logger.error(
                f"WhatsApp Provider Server Error (HTTP {response.status_code})",
                extra={"notification_id": self.notification_id, "channel": "WHATSAPP", "recipient": self.recipient, "status_code": response.status_code, "response": response.text},
            )
            raise Provider5xxError(f"WhatsApp Provider Server Error ({response.status_code}): {response.text}")

        json_response = response.json()
        if json_response.get("code", None) != 100:
            self.logger.error(
                f"WhatsApp provider failed to process message",
                extra={"notification_id": self.notification_id, "channel": "WHATSAPP", "recipient": self.recipient, "provider_response": json_response},
            )
            raise ProviderFailedError(f"Whatsapp Provider Failed to Process Message: {json_response}")

        response.raise_for_status()
        return {"success": True, "provider": "tellix", "response": json_response}
