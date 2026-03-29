"""通知系统：新增 keyword_monitors 和 notifications 两张表

Revision ID: 002_notification_system
Revises: 001_initial
Create Date: 2026-03-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_notification_system"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 创建 keyword_monitors 表
    op.create_table(
        "keyword_monitors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建 notifications 表
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("sent", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # notifications 索引（按 type 和 triggered_at 查询频繁）
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_triggered_at", "notifications", [sa.text("triggered_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_notifications_triggered_at", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("keyword_monitors")
