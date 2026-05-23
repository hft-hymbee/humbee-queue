"""
WhatsApp Template API Routes
=============================
Endpoints to manage WhatsApp templates.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth import require_admin_key, require_shared_key
from core.database import get_db
from core.logging import get_logger
from services.whatsapp_template_service import WhatsAppTemplateService
from api.templates.whatsapp.dtos import WhatsAppTemplateCreate, WhatsAppTemplateUpdate, WhatsAppTemplateResponse


router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Templates"])
logger = get_logger("api.templates.whatsapp")


@router.post(
    "",
    response_model=WhatsAppTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new WhatsApp Template",
    dependencies=[Depends(require_admin_key)],
)
def create_whatsapp_template(
    data: WhatsAppTemplateCreate,
    db: Session = Depends(get_db),
):
    try:
        template = WhatsAppTemplateService.create_whatsapp_template(db, data)
        logger.info(f"Created WhatsApp template: {template.template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error creating WhatsApp template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create WhatsApp template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "",
    response_model=List[WhatsAppTemplateResponse],
    summary="Get all WhatsApp Templates",
    dependencies=[Depends(require_admin_key)],
)
def get_all_whatsapp_templates(
    db: Session = Depends(get_db),
):
    return WhatsAppTemplateService.get_all_whatsapp_templates(db)


@router.get(
    "/{template_id}",
    response_model=WhatsAppTemplateResponse,
    summary="Get a WhatsApp Template by ID",
    dependencies=[Depends(require_shared_key)],
)
def get_whatsapp_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    template = WhatsAppTemplateService.get_whatsapp_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put(
    "/{template_id}",
    response_model=WhatsAppTemplateResponse,
    summary="Update a WhatsApp Template",
    dependencies=[Depends(require_admin_key)],
)
def update_whatsapp_template(
    template_id: str,
    data: WhatsAppTemplateUpdate,
    db: Session = Depends(get_db),
):
    try:
        template = WhatsAppTemplateService.update_whatsapp_template(db, template_id, data)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        logger.info(f"Updated WhatsApp template: {template_id}")
        return template
    except ValueError as e:
        logger.error(f"Validation error updating WhatsApp template {template_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update WhatsApp template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
