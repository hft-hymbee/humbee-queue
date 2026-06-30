"""
Email Template API Routes
=============================
Endpoints to manage Email templates.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth import require_admin_key, require_shared_key
from core.database import get_db
from core.logging import get_logger
from services.email_template_service import EmailTemplateService
from api.templates.email.dtos import EmailTemplateResponse, EmailTemplateCreate, EmailTemplateUpdate


router = APIRouter(prefix="/email", tags=["Email Templates"])
logger = get_logger("api.templates.email")


@router.post(
    "",
    response_model=EmailTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Email Template",
    dependencies=[Depends(require_admin_key)],
)
def create_email_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
):
    try:
        template = EmailTemplateService.create_email_template(db, data)
        logger.info(f"Created Email template: {template.template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error creating Email template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create Email template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=List[EmailTemplateResponse],
    summary="Get all Email Templates",
    dependencies=[Depends(require_admin_key)],
)
def get_all_email_templates(
    db: Session = Depends(get_db),
):
    return EmailTemplateService.get_all_email_templates(db)


@router.get(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Get an Email Template by ID",
    dependencies=[Depends(require_shared_key)],
)
def get_email_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    template = EmailTemplateService.get_email_template(db, template_id)
    if not template:
        logger.warning(
            f"Email template not found: {template_id}",
            extra={"template_id": template_id},
        )
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Update an Email Template",
    dependencies=[Depends(require_admin_key)],
)
def update_email_template(
    template_id: str,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
):
    try:
        template = EmailTemplateService.update_email_template(db, template_id, data)
        if not template:
            logger.warning(
                f"Email template not found for update: {template_id}",
                extra={"template_id": template_id},
            )
            raise HTTPException(status_code=404, detail="Template not found")
        logger.info(f"Updated Email template: {template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error updating Email template {template_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update Email template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
