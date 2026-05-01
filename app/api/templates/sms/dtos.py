"""
SMS Template DTOs
=================
Data transfer objects for creating, updating, and returning SMS templates.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SMSTemplateCreate(BaseModel):
    template_id: str = Field(..., description="Unique ID for the SMS template (e.g. from Telspiel)")
    message_type: str = Field(..., description="Message type, typically 'PM' for promotional etc.")
    content: str = Field(..., description="Template body with {variables} placeholders")
    variables_count: int = Field(default=0, description="Exact number of variables required")


class SMSTemplateUpdate(BaseModel):
    message_type: Optional[str] = Field(None, description="Message type")
    content: Optional[str] = Field(None, description="Template body with {variables} placeholders")
    variables_count: Optional[int] = Field(None, description="Exact number of variables required")


class SMSTemplateResponse(BaseModel):
    template_id: str
    message_type: str
    content: str
    variables_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
