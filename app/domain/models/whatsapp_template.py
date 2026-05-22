"""
WhatsApp Template ORM Model
============================
Database-backed templates for WhatsApp channel.

variables_map maps human-readable variable names to positional indices ("0", "1", ...)
as required by the TelSpiel API's parameterValues dict.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"

    template_id = Column(String(200), primary_key=True)
    template_name = Column(String(100), nullable=False)
    variables_count = Column(Integer, default=0, nullable=False)
    variables_map = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment='{"buyer_name": "0", "invoice_no": "1", ...}',
    )
    has_media = Column(Boolean, default=False, nullable=False)
    media_type = Column(
        String(10),
        nullable=True,
        comment="IMAGE | DOC | VIDEO — null when has_media=False",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return (
            f"<WhatsAppTemplate(template_id={self.template_id}, "
            f"has_media={self.has_media}, media_type={self.media_type})>"
        )
