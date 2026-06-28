"""
Email Template DTOs
=======================
Data transfer objects for creating, updating, and returning Email templates.
"""

from typing import Dict, List, Literal, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class EmailTemplateCreate(BaseModel):
    template_id: str = Field(..., description="Unique ID for the Email template (e.g. CREATE_DP_BCM_TMT)")
    html_template_name: str = Field(..., description="HTML template filename/key used by the renderer (e.g. credit_approved)")
    variables_count: int = Field(default=0, description="Number of variables expected by the template (0 if none)")
    variables_map: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps template variable names to placeholder names. "
            'Example: {"buyer_name": "distributor_name", '
            '"amount": "total_amount"}.'
        ),
    )
    has_media: bool = Field(default=False, description="Whether this template requires a media attachment")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(default=None, description="Required media type when has_media=True")
    table_count: int = Field(default=0, description="Number of dynamic tables expected by the template (0 if none)")
    table_map: Dict[str, List[List[str]]] = Field(
        default_factory=dict,
        description=(
            'Maps table placeholders to their expected column headers. '
            'Each value is a list of column definitions. '
            'Example: {"product_table": [["Product Name", "Quantity", "Price"]], "order_table": [["Order ID", "Amount"]]}'
        ),
    )

    @model_validator(mode="after")
    def validate_media_and_variables(self) -> "EmailTemplateCreate":
        # Media consistency
        if self.has_media and not self.media_type:
            raise ValueError("media_type must be set when has_media is True.")
        if not self.has_media and self.media_type:
            raise ValueError("media_type must be null when has_media is False.")

        # variables_count = 0 => variables_map must be empty
        if self.variables_count == 0:
            if self.variables_map:
                raise ValueError(
                    "variables_map must be empty when variables_count is 0."
                )
            return self

        # variables_count > 0 => variables_map must not be empty
        if not self.variables_map:
            raise ValueError(
                "variables_map must be provided when variables_count is greater than 0."
            )

        # Number of mappings should match variables_count
        if len(self.variables_map) != self.variables_count:
            raise ValueError(
                f"variables_map contains {len(self.variables_map)} variable(s), "
                f"but variables_count is {self.variables_count}."
            )

        # Validate keys and values
        for variable_name, placeholder_name in self.variables_map.items():
            if not variable_name.strip():
                raise ValueError("Variable names cannot be empty.")

            if not placeholder_name.strip():
                raise ValueError(
                    f"Placeholder name for '{variable_name}' cannot be empty."
                )

        return self


class EmailTemplateUpdate(BaseModel):
    html_template_name: Optional[str] = Field(None, description="HTML template filename/key used by the renderer (e.g. credit_approved)")
    variables_count: Optional[int] = Field(None, description="Number of variables")
    variables_map: Optional[Dict[str, str]] = Field(
        None,
        description='Maps template variable names to placeholder names. '
                    'Example: {"buyer_name": "distributor_name", "amount": "total_amount"}.',
    )
    has_media: Optional[bool] = Field(None, description="Whether media is required")
    media_type: Optional[Literal["IMAGE", "DOC", "VIDEO"]] = Field(None, description="Media type")
    table_count: Optional[int] = Field(None, description="Number of dynamic tables expected by the template (0 if none)")
    table_map: Optional[Dict[str, List[List[str]]]] = Field(
        None,
        description=(
            'Maps table placeholders to their expected column headers. '
            'Each value is a list of column definitions. '
            'Example: {"product_table": [["Product Name", "Quantity", "Price"]], "order_table": [["Order ID", "Amount"]]}'
        ),
    )

class EmailTemplateResponse(BaseModel):
    template_id: str
    html_template_name: str
    variables_count: int
    variables_map: Dict[str, str]
    has_media: bool
    media_type: Optional[str]
    table_count: int
    table_map: Dict[str, List[List[str]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
