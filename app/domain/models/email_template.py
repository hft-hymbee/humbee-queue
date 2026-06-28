"""
Email Template ORM Model
========================
Database-backed email template metadata.

This model stores the configuration required to render HTML email templates,
including placeholder variables, optional media, and dynamic tables.

Fields:
- template_id: Unique business identifier for the template.
- html_template_name: HTML template filename/key used by the renderer.
- variables_count: Total number of supported placeholder variables.
- variables_map: Mapping of template variable names to placeholder identifiers
  used by the rendering engine.
  Example:
      {
          "buyer_name": "buyerName",
          "seller_name": "sellerName",
          "invoice_no": "invoiceNumber"
      }

- has_media: Indicates whether the template includes media.
- media_type: Type of media (IMAGE, DOC, VIDEO) when has_media=True.
- table_count: Number of dynamic tables supported by the template.
- table_map: Mapping of table placeholders to their expected column headers.
  Each value is a list of column definitions.
  Example:
      {
          "product_table": [
              ["Product Name", "Quantity", "Price"]
          ],
          "order_table": [
              ["Order ID", "Amount"]
          ]
      }

The actual variable values and table data are supplied at runtime by the
application while rendering the email.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    template_id = Column(String(200), primary_key=True) # Example: "CREATE_DP_BCM_TMT", "CREATE_DP_FMCG_FOOD"
    html_template_name = Column(String(100), nullable=False) # Example: "credit_approved"
    variables_count = Column(Integer, default=0, nullable=False)
    variables_map = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment='{"buyer_name": "Name", "seller_name": "Name", ...}',
    )
    has_media = Column(Boolean, default=False, nullable=False)
    media_type = Column(
        String(10),
        nullable=True,
        comment="IMAGE | DOC | VIDEO — null when has_media=False",
    )
    table_count = Column(Integer, default=0, nullable=False)
    table_map = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment='["product_table": [["Product Name", Quantity]], "order_table": [["Order ID", "Amount"]], ...] - values are lists of lists',
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
            f"<EmailTemplate(template_id={self.template_id}, "
            f"has_media={self.has_media}, media_type={self.media_type}, "
            f"table_count={self.table_count})>"
        )
