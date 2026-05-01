"""
SMS Template ORM Model
======================
Database-backed templates for SMS channel.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, DateTime

from core.database import Base


class SMSTemplate(Base):
    __tablename__ = "sms_templates"

    template_id = Column(String(200), primary_key=True)
    message_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    variables_count = Column(Integer, default=0, nullable=False)
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
        return f"<SMSTemplate(template_id={self.template_id}, type={self.message_type})>"
