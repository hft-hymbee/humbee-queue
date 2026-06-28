"""
Email Channel
=============
Resolves email templates, renders HTML content, and sends via SMTP engine.
"""

import os
from string import Template

from core.database import get_db_session
from channels.base import BaseChannel
from channels.email.engine import EmailEngine
from services.s3_service import S3Service
from services.email_template_service import EmailTemplateService
from api.templates.email.dtos import EmailTemplateResponse


class EmailChannel(BaseChannel):
    """
    Email notification channel.
    Resolves HTML templates with payload variables and sends via SMTP/SES.
    """

    channel_name = "email"
    base_template_path = "channels/email/templates"

    def resolve_template(self) -> EmailTemplateResponse:
        """
        Load and render the email HTML template with payload variables.
        Returns rendered HTML string.
        """
        with get_db_session() as db:
            if not db:
                self.logger.error(
                    "Database session unavailable for Email template resolution",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL"},
                )
                raise ValueError("Database session unavailable for Email template resolution")

            template = EmailTemplateService.get_email_template(db, self.template_id)
            if not template:
                self.logger.error(
                    f"No Email template found for template_id: '{self.template_id}'",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL"},
                )
                raise ValueError(f"No Email template found for template_id: '{self.template_id}'")

            # Materialize template to a Pydantic model to avoid DetachedInstanceError
            # since DB session is closed after this function call
            template_response = EmailTemplateResponse.model_validate(template)

        self.logger.info(
            f"Email template '{self.template_id}' resolved successfully",
            extra={
                "notification_id": self.notification_id, 
                "template_id": self.template_id, 
                "channel": "EMAIL",
                "has_media": template_response.has_media,
                "table_count": template_response.table_count,
            },
        )
        return template_response

    def _resolve_variables(self, template: EmailTemplateResponse) -> dict:
        """
        Resolve template variables from the payload.
        Returns a dict of variable names to values.
        """
        if template.variables_count == 0:
            return {}

        parameter_values = {}
        for name, placeholder_name in template.variables_map.items():
            if name not in self.payload:
                self.logger.error(
                    f"Missing required variable '{name}' for Email template '{self.template_id}'",
                    extra={
                        "notification_id": self.notification_id,
                        "template_id": self.template_id,
                        "channel": "EMAIL",
                        "missing_variable": name,
                        "expected_variables": list(template.variables_map.keys()),
                    },
                )
                raise ValueError(
                    f"Missing required variable '{name}' for Email template '{self.template_id}'. "
                    f"Expected variables: {list(template.variables_map.keys())}"
                )

            parameter_values[placeholder_name] = self.payload[name]

        self.logger.info(
            f"Resolved {len(parameter_values)} variable(s) for Email template '{self.template_id}'",
            extra={
                "notification_id": self.notification_id,
                "template_id": self.template_id,
                "channel": "EMAIL",
                "resolved_variables": list(parameter_values.keys()),
            },
        )
        return parameter_values

    def _resolve_tables(self, template: EmailTemplateResponse) -> dict:
        """
        Resolve table data from the payload.
        Returns a dict of table names to their HTML representations.
        """
        if template.table_count == 0:
            return {}

        table_data = self.payload.get("table_data", {})

        table_values = {}
        for table_name, column_definitions in template.table_map.items():
            if table_name not in table_data:
                self.logger.error(
                    f"Missing required table '{table_name}' for Email template '{self.template_id}'",
                    extra={
                        "notification_id": self.notification_id,
                        "template_id": self.template_id,
                        "channel": "EMAIL",
                        "missing_table": table_name,
                        "expected_tables": list(template.table_map.keys()),
                    },
                )
                raise ValueError(
                    f"Missing required table '{table_name}' for Email template '{self.template_id}'. "
                    f"Expected tables: {list(template.table_map.keys())}"
                )

            # table_map stores a list of column definitions
            if not column_definitions:
                raise ValueError(f"No column definition found for table '{table_name}'.")

            columns = column_definitions[0]

            table_rows = table_data[table_name]

            if len(table_rows) == 0:
                self.logger.error(
                    f"Table '{table_name}' for Email template '{self.template_id}' has no rows",
                    extra={
                        "notification_id": self.notification_id,
                        "template_id": self.template_id,
                        "channel": "EMAIL",
                        "table_name": table_name,
                    },
                )
                raise ValueError(
                    f"Table '{table_name}' for Email template '{self.template_id}' has no rows. "
                    f"At least one row is required."
                )

            # Validate each row has the correct number of columns
            for row_index, row in enumerate(table_rows):
                if len(row) != len(columns):
                    self.logger.error(
                        f"Row {row_index} of table '{table_name}' for Email template '{self.template_id}' has {len(row)} columns, expected {len(columns)}",
                        extra={
                            "notification_id": self.notification_id,
                            "template_id": self.template_id,
                            "channel": "EMAIL",
                            "table_name": table_name,
                            "row_index": row_index,
                            "expected_columns": len(columns),
                            "actual_columns": len(row),
                        },
                    )
                    raise ValueError(
                        f"Row {row_index} of table '{table_name}' for Email template '{self.template_id}' has {len(row)} columns, expected {len(columns)}"
                    )

            # Generate HTML table representation
            table_values[table_name] = "".join(
                "<tr>" + "".join(f'<td style="border: 1px solid black; border-collapse: collapse; padding: 10px;">{cell}</td>' for cell in row) + "</tr>"
                for row in table_rows
            )

        return table_values

    def _resolve_media(self, template) -> list[dict] | None:
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

        Returns a dict formatted for email media block, or None.
        """
        client_medias = self.payload.get("media_payload", [])

        if not template.has_media:
            if client_medias:
                self.logger.error(
                    f"Template '{self.template_id}' is text-only but media payload was provided",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL"},
                )
                raise ValueError(
                    f"Template '{self.template_id}' is a text-only template but "
                    f"media details were provided in the payload. Remove the 'media_payload' key."
                )
            return None

        # Template requires media
        if not client_medias:
            self.logger.error(
                f"Template '{self.template_id}' requires media but 'media_payload' key is missing",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL", "expected_media_type": template.media_type},
            )
            raise ValueError(
                f"Template '{self.template_id}' requires media (type: {template.media_type}) "
                f"but the 'media_payload' key is missing from the payload."
            )

        media_attachments = []
        for media in client_medias:
            media_url = media.get("url")
            media_type = media.get("type")
            media_filename = media.get("file_name")

            if not all([media_url, media_type, media_filename]):
                missing = [
                    k for k, v in {
                        "url": media_url, "type": media_type, "file_name": media_filename
                    }.items() if not v
                ]
                self.logger.error(
                    f"Incomplete media payload for template '{self.template_id}': missing fields {missing}",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL", "missing_fields": missing},
                )
                raise ValueError(
                    f"Incomplete media payload for template '{self.template_id}'. "
                    f"Missing fields: {missing}. Required: 'url', 'type', 'file_name'."
                )

            if media_type != template.media_type:
                self.logger.error(
                    f"Media type mismatch for template '{self.template_id}': expected '{template.media_type}', got '{media_type}'",
                    extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL", "expected": template.media_type, "provided": media_type},
                )
                raise ValueError(
                    f"Media type mismatch for template '{self.template_id}': "
                    f"template expects '{template.media_type}', payload provided '{media_type}'."
                )

            media_attachments.append({
                "type": media_type,
                "url": media_url,
                "filename": media_filename,
            })

        return media_attachments

    def _prepare_mail_body(self, template: EmailTemplateResponse, parameter_values: dict, table_values: dict) -> str:
        """
        Prepare the final email body by substituting variables and tables into the HTML template.
        Returns the rendered HTML string.
        """
        # Load the HTML template file
        template_path = os.path.join(self.base_template_path, f"{template.html_template_name}.html")
        if not os.path.exists(template_path):
            self.logger.error(
                f"HTML template file not found: {template_path}",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL"},
            )
            raise FileNotFoundError(f"HTML template file not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            html_template_content = f.read()

        # Substitute variables
        html_template = Template(html_template_content)
        body_with_vars = html_template.safe_substitute(parameter_values)

        # Substitute tables
        for table_name, table_html in table_values.items():
            placeholder = f"${table_name}"
            body_with_vars = body_with_vars.replace(placeholder, table_html)

        return body_with_vars

    def send(self) -> dict:
        """
        Render template and send email via SMTP engine.
        Returns provider response dict.
        """
        template = self.resolve_template()
        parameter_values = self._resolve_variables(template)
        table_values = self._resolve_tables(template)

        body = self._prepare_mail_body(template, parameter_values, table_values)

        media_attachments = self._resolve_media(template)

        # Attachments array (populated via S3 based on template definition)
        attachments = []
        # 2. S3 Attachment fetching based on template definition
        if media_attachments:
            self.logger.info(
                f"Fetching {len(media_attachments)} media attachment(s) from S3 for Email template '{self.template_id}'",
                extra={"notification_id": self.notification_id, "template_id": self.template_id, "channel": "EMAIL"},
            )
            for media in media_attachments:
                s3_url = media["url"]
                if s3_url:
                    try:
                        file_data = S3Service.download_file(s3_url)
                        attachments.append({
                            "file_name": file_data["filename"],
                            "bytes": file_data["bytes"]
                        })
                        self.logger.info(
                            f"Successfully fetched attachment '{file_data['filename']}' from S3 for Email template '{self.template_id}'",
                            extra={
                                "notification_id": self.notification_id,
                                "template_id": self.template_id,
                                "channel": "EMAIL",
                                "attachment_key": media["url"],
                                "attachment_filename": file_data["filename"],
                            },
                        )
                    except Exception as e:
                        self.logger.error(f"Could not download attachment {media['url']} for email: {e}", extra={
                            "notification_id": self.notification_id,
                            "template_id": self.template_id,
                            "channel": "EMAIL",
                            "attachment_key": media["url"],
                        })
                        raise
        
        engine = EmailEngine()
        result = engine.send(
            recipient=self.recipient,
            subject=self.subject or "Notification",
            body=body,
            attachments=attachments or None,
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
