"""
Email SMTP Engine
=================
Handles SMTP connection and email delivery via AWS SES.
Refactored from the original notification_email/services/email_engine.py.
"""

import smtplib
from base64 import decodebytes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from core.config import settings
from core.logging import get_logger

logger = get_logger("channel.email.engine")


def get_mime_type_from_filename(filename: str) -> Optional[str]:
    """Determine MIME type from file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "csv": "text/csv",
        "heic": "image/heic",
        "mp4": "video/mp4",
        "mkv": "video/x-matroska",
    }
    return mime_map.get(ext)


class EmailEngine:
    """
    SMTP email sender using AWS SES.

    Usage:
        engine = EmailEngine()
        success = engine.send(
            recipient="user@example.com",
            subject="Order Created",
            body="<html>...</html>",
            attachments=[{"file_name": "order.pdf", "base64": "..."}],
        )
    """

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL

    def _connect(self) -> smtplib.SMTP:
        """Establish SMTP connection with TLS."""
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.ehlo()
        server.starttls()
        server.login(self.smtp_username, self.smtp_password)
        return server

    def _build_message(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[List[dict]] = None,
    ) -> str:
        """Build MIME message with optional attachments."""
        message = MIMEMultipart()
        message["From"] = self.from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(body, "html", "utf-8"))

        if attachments:
            for attachment in attachments:
                file_name = attachment.get("file_name", "attachment")
                base64_data = attachment.get("base64", "")
                raw_bytes = attachment.get("bytes", None)
                
                if not base64_data and not raw_bytes:
                    continue

                mime_type = get_mime_type_from_filename(file_name)
                if not mime_type:
                    logger.warning(f"Unknown MIME type for {file_name}, skipping attachment")
                    continue

                main_type, sub_type = mime_type.split("/")
                file_mime = MIMEBase(main_type, sub_type)
                
                if raw_bytes:
                    file_mime.set_payload(raw_bytes)
                else:
                    file_mime.set_payload(decodebytes(bytes(base64_data, "utf-8")))
                    
                encoders.encode_base64(file_mime)
                file_mime.add_header(
                    "Content-Disposition", "attachment", filename=file_name
                )
                message.attach(file_mime)

        return message.as_string()

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        """
        Send an email via SMTP.

        Returns:
            dict with "success" (bool) and optional error info
        """
        server = None
        try:
            server = self._connect()
            message = self._build_message(recipient, subject, body, attachments)
            server.sendmail(self.from_email, recipient, message)
            logger.info(f"Email delivered to {recipient}")
            return {"success": True, "provider": "aws_ses"}
        except Exception as e:
            logger.error(f"Email delivery failed to {recipient}: {e}")
            return {"success": False, "provider": "aws_ses", "error": str(e)}
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
