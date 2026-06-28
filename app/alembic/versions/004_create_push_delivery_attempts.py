"""create push_delivery_attempts table

Revision ID: 004
Revises: 003
Create Date: 2026-06-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_delivery_attempts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "notification_history_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notification_history.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id",    sa.String(100), nullable=True),
        sa.Column("fcm_token",  sa.String(512), nullable=False),
        sa.Column("device_id",  sa.String(255), nullable=True),
        sa.Column("platform",   sa.String(20),  nullable=True),
        sa.Column("status",     sa.String(20),  nullable=False),
        sa.Column("provider_message_id", sa.String(512), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("sent_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_pda_notification_history_id",
        "push_delivery_attempts",
        ["notification_history_id"],
    )
    op.create_index("idx_pda_user_id",   "push_delivery_attempts", ["user_id"])
    op.create_index("idx_pda_fcm_token", "push_delivery_attempts", ["fcm_token"])
    op.create_index("idx_pda_status",    "push_delivery_attempts", ["status"])


def downgrade() -> None:
    op.drop_index("idx_pda_status",                  table_name="push_delivery_attempts")
    op.drop_index("idx_pda_fcm_token",               table_name="push_delivery_attempts")
    op.drop_index("idx_pda_user_id",                 table_name="push_delivery_attempts")
    op.drop_index("idx_pda_notification_history_id", table_name="push_delivery_attempts")
    op.drop_table("push_delivery_attempts")
