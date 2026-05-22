"""create whatsapp_templates table

Revision ID: 003
Revises: 002
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_templates",
        sa.Column("template_id", sa.String(length=200), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("variables_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "variables_map",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment='{"buyer_name": "0", "invoice_no": "1", ...}',
        ),
        sa.Column("has_media", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "media_type",
            sa.String(length=10),
            nullable=True,
            comment="IMAGE | DOC | VIDEO — null when has_media=false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("template_id"),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_templates")
