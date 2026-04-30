"""create notification_history table

Revision ID: 001
Revises:
Create Date: 2026-04-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("template_id", sa.String(200), nullable=True),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("provider_response", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("max_retries", sa.Integer, server_default="3"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # Individual indexes
    op.create_index("idx_nh_user_id", "notification_history", ["user_id"])
    op.create_index("idx_nh_status", "notification_history", ["status"])
    op.create_index("idx_nh_event_type", "notification_history", ["event_type"])
    op.create_index("idx_nh_channel", "notification_history", ["channel"])
    op.create_index("idx_nh_created_at", "notification_history", ["created_at"])
    op.create_index("idx_nh_request_id", "notification_history", ["request_id"])
    op.create_index("idx_nh_recipient", "notification_history", ["recipient"])

    # Composite index
    op.create_index("idx_nh_user_channel_status", "notification_history", ["user_id", "channel", "status"])


def downgrade() -> None:
    op.drop_index("idx_nh_user_channel_status", table_name="notification_history")
    op.drop_index("idx_nh_recipient", table_name="notification_history")
    op.drop_index("idx_nh_request_id", table_name="notification_history")
    op.drop_index("idx_nh_created_at", table_name="notification_history")
    op.drop_index("idx_nh_channel", table_name="notification_history")
    op.drop_index("idx_nh_event_type", table_name="notification_history")
    op.drop_index("idx_nh_status", table_name="notification_history")
    op.drop_index("idx_nh_user_id", table_name="notification_history")
    op.drop_table("notification_history")
