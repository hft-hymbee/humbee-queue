"""
SMS Template API Routes
=======================
Endpoints to manage SMS templates.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth import require_admin_key, require_shared_key
from core.database import get_db
from core.logging import get_logger
from services.sms_template_service import SmsTemplateService
from api.templates.sms.dtos import SMSTemplateCreate, SMSTemplateUpdate, SMSTemplateResponse


router = APIRouter(prefix="/sms", tags=["SMS Templates"])
logger = get_logger("api.templates.sms")


@router.post(
    "",
    response_model=SMSTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SMS Template",
    dependencies=[Depends(require_admin_key)],
)
def create_sms_template(
    data: SMSTemplateCreate,
    db: Session = Depends(get_db),
):
    try:
        template = SmsTemplateService.create_sms_template(db, data)
        logger.info(f"Created SMS template: {template.template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error creating SMS template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create SMS template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=List[SMSTemplateResponse],
    summary="Get all SMS Templates",
    dependencies=[Depends(require_admin_key)],
)
def get_all_sms_templates(
    db: Session = Depends(get_db),
):
    return SmsTemplateService.get_all_sms_templates(db)


@router.get(
    "/{template_id}",
    response_model=SMSTemplateResponse,
    summary="Get an SMS Template by ID",
    dependencies=[Depends(require_shared_key)],
)
def get_sms_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    template = SmsTemplateService.get_sms_template(db, template_id)
    if not template:
        logger.warning(
            f"SMS template not found: {template_id}",
            extra={"template_id": template_id},
        )
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put(
    "/{template_id}",
    response_model=SMSTemplateResponse,
    summary="Update an SMS Template",
    dependencies=[Depends(require_admin_key)],
)
def update_sms_template(
    template_id: str,
    data: SMSTemplateUpdate,
    db: Session = Depends(get_db),
):
    try:
        template = SmsTemplateService.update_sms_template(db, template_id, data)
        if not template:
            logger.warning(
                f"SMS template not found for update: {template_id}",
                extra={"template_id": template_id},
            )
            raise HTTPException(status_code=404, detail="Template not found")
        logger.info(f"Updated SMS template: {template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error updating SMS template {template_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update SMS template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
