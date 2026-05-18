"""
API Key Authentication
======================
FastAPI dependency functions for x-api-key header validation.

Two access tiers:
  - Shared (Team) Key  : accepted by require_shared_key
  - Admin Keys         : accepted by both require_shared_key and require_admin_key

Admin keys can call both shared-tier and admin-tier endpoints.
Shared key can only call shared-tier endpoints.

Adding a new admin:
  Add an entry to secrets.json["api_keys"]["admin_keys"] — no code changes needed.

Usage:
    from core.auth import require_shared_key, require_admin_key

    @router.get("/some-endpoint")
    def my_endpoint(_: None = Depends(require_shared_key)):
        ...
"""

from typing import Optional

from fastapi import Header, HTTPException

from core.config import settings
from core.logging import get_logger


logger = get_logger("core.auth")


def require_shared_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    Accepts:
      - The shared team key
      - Any valid admin key (admins can do everything shared users can)

    Raises:
      401 if the x-api-key header is absent entirely.
      403 if the key is present but invalid or insufficient tier.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="x-api-key header is required")

    if x_api_key == settings.SHARED_API_KEY:
        return

    if x_api_key in settings.ADMIN_KEY_VALUES:
        admin_name = settings.ADMIN_KEY_LOOKUP.get(x_api_key, "unknown")
        logger.info(f"Admin '{admin_name}' accessing shared-tier endpoint")
        return

    raise HTTPException(status_code=403, detail="Invalid API key")


def require_admin_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    Accepts only valid admin keys.
    The shared team key is NOT accepted here.

    Raises:
      401 if the x-api-key header is absent entirely.
      403 if the key is present but invalid or is only a shared-tier key.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="x-api-key header is required")

    if x_api_key in settings.ADMIN_KEY_VALUES:
        admin_name = settings.ADMIN_KEY_LOOKUP.get(x_api_key, "unknown")
        logger.info(f"Admin '{admin_name}' accessing admin-tier endpoint")
        return

    raise HTTPException(status_code=403, detail="Invalid API key")
