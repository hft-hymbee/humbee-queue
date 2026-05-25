"""
WhatsApp Template Service
==========================
Handles database operations and validation for WhatsApp templates.

Key design:
- variables_map maps human-readable names → positional indices ("0", "1", ...)
  so callers can use meaningful keys; the channel translates them at send time.
- has_media + media_type are enforced to be consistent (if has_media, media_type required).
"""
import json
from typing import List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.logging import get_logger
from core.redis_client import redis_client
from domain.models import WhatsAppTemplate
from api.templates.whatsapp.dtos import (
    WhatsAppTemplateCreate,
    WhatsAppTemplateUpdate,
    WhatsAppTemplateResponse,
)

logger = get_logger(__name__)

CACHE_KEY_PREFIX = "wa_template"


class WhatsAppTemplateService:

    @staticmethod
    def validate_variables_count(variables_map: dict, variables_count: int):
        """
        Validates that the total number of positional slots in variables_map matches variables_count.

        Each variable's value may be a single position string ("0") or a list of positions (["0", "3"]).
        The sum of all positions — not the number of unique variable names — must equal variables_count.
        """
        total_positions = sum(
            len(v) if isinstance(v, list) else 1
            for v in variables_map.values()
        )
        if total_positions != variables_count:
            raise ValueError(
                f"Invalid variables_count. variables_map resolves to {total_positions} total "
                f"position(s), but variables_count is {variables_count}. They must match."
            )

    @staticmethod
    def validate_media_consistency(has_media: bool, media_type: str = None):
        """
        Validates that media_type is set when has_media is True and null when has_media is False.
        """
        if has_media and not media_type:
            raise ValueError("media_type must be set when has_media is True.")
        if not has_media and media_type:
            raise ValueError("media_type must be null when has_media is False.")

    @classmethod
    def create_whatsapp_template(
        cls, db: Session, data: WhatsAppTemplateCreate
    ) -> WhatsAppTemplate:
        # Validate media consistency
        cls.validate_variables_count(data.variables_map, data.variables_count)
        
        # Validate media consistency
        cls.validate_media_consistency(data.has_media, data.media_type)

        # Check if template already exists
        existing = cls.get_whatsapp_template(db, data.template_id)
        if existing:
            raise ValueError(f"WhatsApp Template with ID '{data.template_id}' already exists.")

        template = WhatsAppTemplate(
            template_id=data.template_id,
            template_name=data.template_name,
            variables_count=data.variables_count,
            variables_map=data.variables_map,
            has_media=data.has_media,
            media_type=data.media_type,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"WhatsApp Template '{data.template_id}' created.")
        return template

    @classmethod
    def get_whatsapp_template(
        cls, db: Session, template_id: str
    ) -> Optional[WhatsAppTemplate]:
        # 1. Try cache
        cache_key = f"{CACHE_KEY_PREFIX}:{template_id}"
        if redis_client.connection:
            try:
                cached_data = redis_client.connection.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"WhatsApp Template '{template_id}' found in cache.")
                    return WhatsAppTemplate(**data)
            except Exception:
                pass  # Fall through to DB on any cache error

        # 2. Try DB
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.template_id == template_id).first()
        if template:
            logger.info(f"WhatsApp Template '{template_id}' found in database.")

        # 3. Save to cache
        if template and redis_client.connection:
            try:
                template_data = WhatsAppTemplateResponse.model_validate(template).model_dump(mode="json")
                redis_client.connection.setex(
                    cache_key,
                    settings.TEMPLATE_CACHE_TTL,
                    json.dumps(template_data),
                )
                logger.info(f"WhatsApp Template '{template_id}' saved to cache.")
            except Exception:
                logger.error(f"WhatsApp Template '{template_id}' failed to save to cache.")
                pass

        return template

    @classmethod
    def get_all_whatsapp_templates(cls, db: Session) -> List[WhatsAppTemplate]:
        return db.query(WhatsAppTemplate).all()

    @classmethod
    def update_whatsapp_template(
        cls, db: Session, template_id: str, data: WhatsAppTemplateUpdate
    ) -> Optional[WhatsAppTemplate]:
        template = cls.get_whatsapp_template(db, template_id)
        if not template:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Merge with existing values for cross-field validation
        new_has_media = update_data.get("has_media", template.has_media)
        new_media_type = update_data.get("media_type", template.media_type)
        new_variables_count = update_data.get("variables_count", template.variables_count)
        new_variables_map = update_data.get("variables_map", template.variables_map)

        # Validate variables count
        if "variables_count" in update_data or "variables_map" in update_data:
            cls.validate_variables_count(new_variables_map, new_variables_count)
            
        # Validate media consistency
        if "has_media" in update_data or "media_type" in update_data:
            cls.validate_media_consistency(new_has_media, new_media_type)

        for key, value in update_data.items():
            setattr(template, key, value)

        db.commit()
        db.refresh(template)

        # Invalidate cache
        if redis_client.connection:
            try:
                redis_client.connection.delete(f"{CACHE_KEY_PREFIX}:{template_id}")
                logger.info(f"WhatsApp Template '{template_id}' evicted from cache.")
            except Exception:
                logger.error(f"WhatsApp Template '{template_id}' failed to evict from cache.")
                pass

        return template
