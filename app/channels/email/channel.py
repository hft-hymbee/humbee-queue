"""
Email Channel
=============
Resolves email templates, renders HTML content, and sends via SMTP engine.
"""

import os
from string import Template

from channels.base import BaseChannel
from channels.email.engine import EmailEngine
from channels.email.templates import EMAIL_TEMPLATES
from services.s3_service import S3Service


class EmailChannel(BaseChannel):
    """
    Email notification channel.
    Resolves HTML templates with payload variables and sends via SMTP/SES.
    """

    channel_name = "email"

    def resolve_template(self) -> str:
        """
        Load and render the email HTML template with payload variables.
        Returns rendered HTML string.
        """
        template_config = EMAIL_TEMPLATES.get(self.template_id)
        if not template_config:
            raise ValueError(
                f"No email template found for template_id: {self.template_id}"
            )
        
        template_path = template_config["html_path"]

        if not os.path.exists(template_path):
            raise FileNotFoundError(
                f"Email template file not found: {template_path}"
            )

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Render template with payload
        template = Template(html_content)
        rendered = template.safe_substitute(**self._prepare_template_vars())

        self.logger.info(
            "Email template rendered",
            extra={
                "notification_id": self.notification_id,
                "template_id": self.template_id,
                "channel": "EMAIL",
            },
        )
        return rendered

    def send(self) -> dict:
        """
        Render template and send email via SMTP engine.
        Returns provider response dict.
        """
        body = self.resolve_template()
        template_config = EMAIL_TEMPLATES.get(self.template_id)
        
        # Attachments array (populated via S3 based on template definition)
        attachments = []
        
        # 2. S3 Attachment fetching based on template definition
        if template_config.get("has_attachment"):
            payload_keys = template_config.get("attachment_payload_keys", [])
            for key in payload_keys:
                s3_url = self.payload.get(key)
                if s3_url:
                    try:
                        file_data = S3Service.download_file(s3_url)
                        attachments.append({
                            "file_name": file_data["filename"],
                            "bytes": file_data["bytes"]
                        })
                    except Exception as e:
                        self.logger.error(f"Could not download attachment {key} for email: {e}")
                        raise

        engine = EmailEngine()
        result = engine.send(
            recipient=self.recipient,
            subject=self.subject or "Notification",
            body=body,
            attachments=attachments if attachments else None,
        )

        log_method = self.logger.info if result.get("success") else self.logger.error
        log_method(
            f"Email {'sent' if result.get('success') else 'failed'} to {self.recipient}",
            extra={
                "notification_id": self.notification_id,
                "channel": "EMAIL",
                "template_id": self.template_id,
                "recipient": self.recipient,
                "status": "SENT" if result.get("success") else "FAILED",
            },
        )

        if not result.get("success"):
            raise Exception(f"Email delivery failed: {result.get('error', 'Unknown error')}")

        return result

    def _prepare_template_vars(self) -> dict:
        """
        Prepare template variables from the payload.
        Handles table data generation for order-related templates.
        """
        template_vars = dict(self.payload)

        # Generate HTML table data if product_details present
        product_details = self.payload.get("product_details", [])
        if product_details:
            table_rows = []
            for product in product_details:
                product_name = product.get("product_name", "")
                quantity = product.get("quantity", 0)
                unit = product.get("unit", "")
                row = (
                    f'<tr>'
                    f'<td style="border: 1px solid black; border-collapse: collapse; padding: 10px;">{product_name}</td>'
                    f'<td style="border: 1px solid black; border-collapse: collapse; padding: 10px;">{quantity} {unit}</td>'
                    f'</tr>'
                )
                table_rows.append(row)
            template_vars["dispatch_plan_table"] = "".join(table_rows)

        return template_vars
