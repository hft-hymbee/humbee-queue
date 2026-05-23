"""
WhatsApp Template DTOs
=======================
Data transfer objects for creating, updating, and returning WhatsApp templates.
"""

from typing import Dict, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class WhatsAppTemplateCreate(BaseModel):
    template_id: str = Field(..., description="Unique ID for the WhatsApp template (e.g. from Telspiel)")
    template_name: str = Field(..., description="Friendly name for the template")
    variables_count: int = Field(default=0, description="Number of positional variables expected by the template (0 if none)")
    variables_map: Dict[str, str] = Field(default_factory=dict, description='Maps meaningful variable names to positional indices: {"buyer_name": "0", "amount": "1"}')
    has_media: bool = Field(default=False, description="Whether this template requires a media attachment")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(default=None, description="Required media type when has_media=True")

    @model_validator(mode="after")
    def validate_media_and_variables(self) -> "WhatsAppTemplateCreate":
        # Media consistency
        if self.has_media and not self.media_type:
            raise ValueError("media_type must be set when has_media is True.")
        if not self.has_media and self.media_type:
            raise ValueError("media_type must be null when has_media is False.")

        # variables_map length must match variables_count
        if len(self.variables_map) != self.variables_count:
            raise ValueError(
                f"variables_map has {len(self.variables_map)} entries but "
                f"variables_count is {self.variables_count}. They must match."
            )
        return self


class WhatsAppTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, description="Friendly name for the template")
    variables_count: Optional[int] = Field(None, description="Number of variables")
    variables_map: Optional[Dict[str, str]] = Field(None, description="Named→positional variable map")
    has_media: Optional[bool] = Field(None, description="Whether media is required")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(None, description="Media type")


class WhatsAppTemplateResponse(BaseModel):
    template_id: str
    template_name: str
    variables_count: int
    variables_map: Dict[str, str]
    has_media: bool
    media_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
