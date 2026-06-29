"""
Email Template Service
==========================
Handles database operations and validation for Email templates.

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
from domain.models import EmailTemplate
from api.templates.email.dtos import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
)

logger = get_logger(__name__)

CACHE_KEY_PREFIX = "email_template"


class EmailTemplateService:

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

    @staticmethod
    def validate_table_consistency(table_map: dict, table_count: int):
        """
        Validates that the number of tables in table_map matches table_count.
        """
        if len(table_map) != table_count:
            raise ValueError(
                f"Invalid table_count. table_map contains {len(table_map)} table(s), "
                f"but table_count is {table_count}. They must match."
            )

    @classmethod
    def create_email_template(
        cls, db: Session, data: EmailTemplateCreate
    ) -> EmailTemplate:
        # Validate variables consistency
        cls.validate_variables_count(data.variables_map, data.variables_count)
        
        # Validate media consistency
        cls.validate_media_consistency(data.has_media, data.media_type)

        # Validate table consistency
        cls.validate_table_consistency(data.table_map, data.table_count)

        # Check if template already exists
        existing = cls.get_email_template(db, data.template_id)
        if existing:
            raise ValueError(f"Email Template with ID '{data.template_id}' already exists.")

        template = EmailTemplate(
            template_id=data.template_id,
            html_template_name=data.html_template_name,
            variables_count=data.variables_count,
            variables_map=data.variables_map,
            has_media=data.has_media,
            media_type=data.media_type,
            table_count=data.table_count,
            table_map=data.table_map,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"Email Template '{data.template_id}' created.")
        return template

    @classmethod
    def get_email_template(
        cls, db: Session, template_id: str
    ) -> Optional[EmailTemplate]:
        # 1. Try cache
        cache_key = f"{CACHE_KEY_PREFIX}:{template_id}"
        if redis_client.connection:
            try:
                cached_data = redis_client.connection.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"Email Template '{template_id}' found in cache.")
                    return EmailTemplate(**data)
            except Exception:
                pass  # Fall through to DB on any cache error

        # 2. Try DB
        template = db.query(EmailTemplate).filter(EmailTemplate.template_id == template_id).first()
        if template:
            logger.info(f"Email Template '{template_id}' found in database.")

        # 3. Save to cache
        if template and redis_client.connection:
            try:
                template_data = EmailTemplateResponse.model_validate(template).model_dump(mode="json")
                redis_client.connection.setex(
                    cache_key,
                    settings.TEMPLATE_CACHE_TTL,
                    json.dumps(template_data),
                )
                logger.info(f"Email Template '{template_id}' saved to cache.")
            except Exception:
                logger.error(f"Email Template '{template_id}' failed to save to cache.")
                pass

        return template

    @classmethod
    def get_all_email_templates(cls, db: Session) -> List[EmailTemplate]:
        return db.query(EmailTemplate).all()

    @classmethod
    def update_email_template(
        cls, db: Session, template_id: str, data: EmailTemplateUpdate
    ) -> Optional[EmailTemplate]:
        template = (
            db.query(EmailTemplate)
            .filter(EmailTemplate.template_id == template_id)
            .first()
        )
        if not template:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Merge with existing values for cross-field validation
        new_has_media = update_data.get("has_media", template.has_media)
        new_media_type = update_data.get("media_type", template.media_type)
        new_variables_count = update_data.get("variables_count", template.variables_count)
        new_variables_map = update_data.get("variables_map", template.variables_map)
        new_table_count = update_data.get("table_count", template.table_count)
        new_table_map = update_data.get("table_map", template.table_map)

        # Validate variables count
        if "variables_count" in update_data or "variables_map" in update_data:
            cls.validate_variables_count(new_variables_map, new_variables_count)

        # Validate media consistency
        if "has_media" in update_data or "media_type" in update_data:
            cls.validate_media_consistency(new_has_media, new_media_type)

        # Validate table consistency
        if "table_count" in update_data or "table_map" in update_data:
            cls.validate_table_consistency(new_table_map, new_table_count)

        for key, value in update_data.items():
            setattr(template, key, value)

        db.commit()
        db.refresh(template)

        # Invalidate cache
        if redis_client.connection:
            try:
                redis_client.connection.delete(f"{CACHE_KEY_PREFIX}:{template_id}")
                logger.info(f"Email Template '{template_id}' evicted from cache.")
            except Exception:
                logger.error(f"Email Template '{template_id}' failed to evict from cache.")
                pass

        return template
