"""初始迁移：创建三张核心表

Revision ID: 001_initial
Revises:
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 collected_data 表
    op.create_table(
        "collected_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("title", sa.String(), sa.Computed("data->>'title'", persisted=True)),
        sa.Column("url", sa.String(), sa.Computed("data->>'url'", persisted=True)),
        sa.PrimaryKeyConstraint("id"),
    )

    # collected_data 索引
    op.create_index("idx_source_time", "collected_data", ["source", sa.text("collected_at DESC")])
    op.create_index("idx_category_time", "collected_data", ["category", sa.text("collected_at DESC")])
    op.create_index("idx_data_gin", "collected_data", ["data"], postgresql_using="gin")

    # 创建 spider_registry 表
    op.create_table(
        "spider_registry",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("engine", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32)),
        sa.Column("schedule", sa.String(length=64)),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("config", postgresql.JSONB()),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(length=16)),
        sa.Column("item_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    # 创建 spider_runs 表
    op.create_table(
        "spider_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("spider_name", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("duration_ms", sa.Integer()),
        sa.PrimaryKeyConstraint("id"),
    )

    # spider_runs 索引
    op.create_index("ix_spider_runs_spider_name", "spider_runs", ["spider_name"])


def downgrade() -> None:
    # 按依赖顺序删除

    # 先删除 spider_runs（引用 spider_registry）
    op.drop_index("ix_spider_runs_spider_name", table_name="spider_runs")
    op.drop_table("spider_runs")

    # 删除 spider_registry
    op.drop_table("spider_registry")

    # 删除 collected_data
    op.drop_index("idx_data_gin", table_name="collected_data")
    op.drop_index("idx_category_time", table_name="collected_data")
    op.drop_index("idx_source_time", table_name="collected_data")
    op.drop_table("collected_data")
