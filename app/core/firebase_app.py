"""
Firebase App
============
Singleton Firebase Admin SDK app initializer.
Initialized once per Celery worker process on first use.
Uses service account credentials loaded directly from settings (no file I/O).

Usage:
    from core.firebase_app import get_firebase_app
    get_firebase_app()  # ensure initialized before any messaging calls
"""

import firebase_admin
from firebase_admin import credentials

from core.config import settings
from core.logging import get_logger

logger = get_logger("core.firebase")

_default_app = None


def get_firebase_app() -> firebase_admin.App:
    """
    Return the Firebase Admin app singleton.

    Initializes on first call using credentials from settings.FCM_SERVICE_ACCOUNT_JSON.
    Each subsequent call is a no-op and returns the cached app instance.

    Thread-safety: Celery workers are multi-process (not multi-threaded by default),
    so each worker process gets its own _default_app in its own memory space — no
    lock needed.

    Raises:
        RuntimeError: If FCM_SERVICE_ACCOUNT_JSON is not configured in secrets.
    """
    global _default_app

    if _default_app is None:
        if not settings.FCM_SERVICE_ACCOUNT_JSON:
            logger.error("FCM_SERVICE_ACCOUNT_JSON is not configured. Add 'firebase.service_account_json' to secrets")
            raise RuntimeError(
                "FCM_SERVICE_ACCOUNT_JSON is not configured. "
                "Add 'firebase.service_account_json' to secrets."
            )

        # credentials.Certificate() accepts both a file path and a plain dict.
        # We pass the dict loaded from secrets directly — no temp file needed.
        cred = credentials.Certificate(settings.FCM_SERVICE_ACCOUNT_JSON)
        _default_app = firebase_admin.initialize_app(cred)

        logger.info(
            "Firebase Admin app initialized",
            extra={"app_name": _default_app.name},
        )

    return _default_app
