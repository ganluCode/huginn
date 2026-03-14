"""SQLAlchemy 2.0 数据模型"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.schema import Computed


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class CollectedData(Base):
    """采集数据主表"""
    __tablename__ = "collected_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 生成列：从 JSONB data 字段提取常用字段
    title: Mapped[str | None] = mapped_column(
        String, Computed("data->>'title'", persisted=True)
    )
    url: Mapped[str | None] = mapped_column(
        String, Computed("data->>'url'", persisted=True)
    )


class SpiderRegistry(Base):
    """Spider 注册表"""
    __tablename__ = "spider_registry"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    engine: Mapped[str] = mapped_column(String(16), nullable=False)  # "scrapy" | "rpa"
    category: Mapped[str | None] = mapped_column(String(32))
    schedule: Mapped[str | None] = mapped_column(String(64))  # cron 表达式
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))
    item_count: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )


class SpiderRun(Base):
    """Spider 运行日志"""
    __tablename__ = "spider_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    spider_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("spider_registry.name"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # "running" | "success" | "failed"
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
