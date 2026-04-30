"""
Structured JSON Logger
======================
Produces JSON-formatted log output compatible with CloudWatch Logs.
Every log entry includes correlation fields for searchability.

Usage:
    from core.logging import get_logger
    logger = get_logger("channel.email")
    logger.info("Email sent", extra={"notification_id": "uuid-123", "channel": "EMAIL"})
"""

import json
import logging
import sys
import os
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    CloudWatch agent parses these automatically.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "filename": record.filename,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "message": record.getMessage(),
        }

        # Add correlation fields if present in extra
        correlation_fields = [
            "request_id", "notification_id", "user_id",
            "channel", "event_type", "status",
            "recipient", "template_id",
            "duration_ms", "error_message", "retry_count",
            "application_mode",
        ]
        for field in correlation_fields:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class PrettyFormatter(logging.Formatter):
    """
    Human-readable formatter for local development.
    Includes correlation fields inline.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build context string from extra fields
        context_parts = []
        for field in ["request_id", "notification_id", "channel", "status", "user_id"]:
            value = getattr(record, field, None)
            if value is not None:
                context_parts.append(f"{field}={value}")
        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        msg = f"{color}{timestamp} {record.levelname}:: [{record.filename}:{record.lineno} in {record.funcName}()]{self.RESET}{context} {record.getMessage()}"

        if record.exc_info and record.exc_info[0] is not None:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging():
    """
    Configure root logger based on ENV.
    LOCAL → PrettyFormatter (human-readable)
    PROD  → JSONFormatter (CloudWatch-compatible)
    """
    env = os.getenv("ENV", "LOCAL")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add stdout handler with appropriate formatter
    handler = logging.StreamHandler(sys.stdout)
    if env == "LOCAL":
        handler.setFormatter(PrettyFormatter())
    else:
        handler.setFormatter(JSONFormatter())

    root_logger.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("kombu").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger. Call setup_logging() first (done at app startup).

    Args:
        name: Logger name, typically module path like "channel.email" or "service.dispatcher"
    """
    return logging.getLogger(name)


# Auto-setup on import
setup_logging()
