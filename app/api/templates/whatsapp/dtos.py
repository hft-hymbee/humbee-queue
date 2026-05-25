"""
WhatsApp Template DTOs
=======================
Data transfer objects for creating, updating, and returning WhatsApp templates.
"""

from typing import Dict, List, Literal, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class WhatsAppTemplateCreate(BaseModel):
    template_id: str = Field(..., description="Unique ID for the WhatsApp template (e.g. from Telspiel)")
    template_name: str = Field(..., description="Friendly name for the template")
    variables_count: int = Field(default=0, description="Number of positional variables expected by the template (0 if none)")
    variables_map: Dict[str, Union[str, List[str]]] = Field(
        default_factory=dict,
        description=(
            'Maps meaningful variable names to positional indices. '
            'A single position: {"buyer_name": "0"} or multiple positions: {"buyer_name": ["0", "3"], "amount": "1"}. '
            'Single strings are normalised to lists automatically.'
        ),
    )
    has_media: bool = Field(default=False, description="Whether this template requires a media attachment")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(default=None, description="Required media type when has_media=True")

    @model_validator(mode="after")
    def validate_media_and_variables(self) -> "WhatsAppTemplateCreate":
        # Media consistency
        if self.has_media and not self.media_type:
            raise ValueError("media_type must be set when has_media is True.")
        if not self.has_media and self.media_type:
            raise ValueError("media_type must be null when has_media is False.")

        # Normalise all values to List[str] so downstream code (channel, service)
        # always works with a uniform type, regardless of how the caller submitted it.
        self.variables_map = {
            name: ([pos] if isinstance(pos, str) else pos)
            for name, pos in self.variables_map.items()
        }

        # variables_count must equal the TOTAL number of positions across all variables,
        # not just the number of unique variable names.
        total_positions = sum(len(positions) for positions in self.variables_map.values())
        if total_positions != self.variables_count:
            raise ValueError(
                f"variables_map resolves to {total_positions} total position(s) but "
                f"variables_count is {self.variables_count}. They must match."
            )
        return self


class WhatsAppTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, description="Friendly name for the template")
    variables_count: Optional[int] = Field(None, description="Number of variables")
    variables_map: Optional[Dict[str, Union[str, List[str]]]] = Field(
        None,
        description='Named→positional variable map. Accepts "0" or ["0", "3"] per variable.',
    )
    has_media: Optional[bool] = Field(None, description="Whether media is required")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(None, description="Media type")


class WhatsAppTemplateResponse(BaseModel):
    template_id: str
    template_name: str
    variables_count: int
    variables_map: Dict[str, Union[str, List[str]]]
    has_media: bool
    media_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
