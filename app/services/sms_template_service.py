"""
SMS Template Service
====================
Handles database operations and validation for SMS templates.
"""
import json
import string
from typing import List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.logging import get_logger
from core.redis_client import redis_client
from domain.models import SMSTemplate
from api.templates.sms.dtos import SMSTemplateCreate, SMSTemplateUpdate, SMSTemplateResponse

logger = get_logger(__name__)


class SmsTemplateService:

    @staticmethod
    def validate_template_variables(content: str, expected_count: int):
        """
        Parses the content string to extract {variables} and validates
        that the number of distinct variables exactly matches expected_count.
        """
        # Parse the format string. formatter.parse returns tuples of (literal_text, field_name, format_spec, conversion)
        parsed_fields = [
            fname for _, fname, _, _ in string.Formatter().parse(content) if fname
        ]
        
        # Count distinct field names
        distinct_vars = set(parsed_fields)
        actual_count = len(distinct_vars)
        
        if actual_count != expected_count:
            raise ValueError(
                f"Variable count mismatch. Template requires {expected_count} variables "
                f"but content contains {actual_count} distinct variables: {distinct_vars}"
            )

    @classmethod
    def create_sms_template(cls, db: Session, data: SMSTemplateCreate) -> SMSTemplate:
        # Validate variables count
        cls.validate_template_variables(data.content, data.variables_count)
        
        # Check if already exists
        existing = cls.get_sms_template(db, data.template_id)
        if existing:
            raise ValueError(f"SMS Template with ID {data.template_id} already exists.")
            
        template = SMSTemplate(
            template_id=data.template_id,
            template_name=data.template_name,
            message_type=data.message_type,
            content=data.content,
            variables_count=data.variables_count,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @classmethod
    def get_sms_template(cls, db: Session, template_id: str) -> Optional[SMSTemplate]:
        # 1. Try Cache
        cache_key = f"sms_template:{template_id}"
        if redis_client.connection:
            try:
                cached_data = redis_client.connection.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"SMS Template with ID {template_id} found in cache.")
                    # Create an ORM-like object from cached data
                    return SMSTemplate(**data)
            except Exception:
                pass # Fallback to DB on cache error

        # 2. Try DB
        template = db.query(SMSTemplate).filter(SMSTemplate.template_id == template_id).first()
        if template:
            logger.info(f"SMS Template with ID {template_id} found in database.")

        # 3. Save to Cache
        if template and redis_client.connection:
            try:
                # Use DTO to serialize
                template_data = SMSTemplateResponse.model_validate(template).model_dump(mode="json")
                redis_client.connection.setex(
                    cache_key,
                    settings.TEMPLATE_CACHE_TTL,
                    json.dumps(template_data)
                )
                logger.info(f"SMS Template with ID {template_id} saved to cache.")
            except Exception:
                logger.error(f"SMS Template with ID {template_id} failed to save to cache.")
                pass

        return template

    @classmethod
    def get_all_sms_templates(cls, db: Session) -> List[SMSTemplate]:
        return db.query(SMSTemplate).all()

    @classmethod
    def update_sms_template(cls, db: Session, template_id: str, data: SMSTemplateUpdate) -> Optional[SMSTemplate]:
        template = cls.get_sms_template(db, template_id)
        if not template:
            return None
            
        update_data = data.model_dump(exclude_unset=True)
        
        # If content or variables_count are updated, re-validate
        new_content = update_data.get("content", template.content)
        new_count = update_data.get("variables_count", template.variables_count)
        
        if "content" in update_data or "variables_count" in update_data:
            cls.validate_template_variables(new_content, new_count)
            
        for key, value in update_data.items():
            setattr(template, key, value)
            
        db.commit()
        db.refresh(template)

        # Invalidate Cache
        if redis_client.connection:
            try:
                redis_client.connection.delete(f"sms_template:{template_id}")
                logger.info(f"SMS Template with ID {template_id} deleted from cache.")
            except Exception:
                logger.error(f"SMS Template with ID {template_id} failed to delete from cache.")
                pass

        return template
