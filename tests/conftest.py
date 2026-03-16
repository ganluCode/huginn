"""Pytest 配置和共享 fixtures"""

import json
import sys
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import TypeDecorator

# 加载 .env.test 配置（在导入 huginn 模块之前）
_env_test = Path(__file__).resolve().parent.parent / ".env.test"
load_dotenv(_env_test, override=True)


class StringJSON(TypeDecorator):
    """JSON type for SQLite that stores as string.

    SQLite doesn't have native JSON support like PostgreSQL's JSONB.
    This type decorator stores JSON as TEXT and handles serialization.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python dict to JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        """Convert JSON string from storage to Python dict."""
        if value is None:
            return None
        return json.loads(value)


# Test-specific models for SQLite compatibility
class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class SpiderRegistry(Base):
    """Spider 注册表 - SQLite 兼容版本"""
    __tablename__ = "spider_registry"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    engine: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str | None] = mapped_column(String(32))
    schedule: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(StringJSON, nullable=True)
    last_run_at: Mapped[DateTime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=lambda: datetime.now())


class SpiderRun(Base):
    """Spider 运行日志 - SQLite 兼容版本"""
    __tablename__ = "spider_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spider_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("spider_registry.name"), nullable=False, index=True
    )
    started_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class CollectedData(Base):
    """采集数据主表 - SQLite 兼容版本"""
    __tablename__ = "collected_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    collected_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    data: Mapped[dict] = mapped_column(StringJSON, nullable=False)


# Import test settings and replace the models in huginn.core.models
from huginn.core import models as huginn_models  # noqa: E402

# Replace the base and models for testing
huginn_models.Base = Base
huginn_models.SpiderRegistry = SpiderRegistry
huginn_models.SpiderRun = SpiderRun
huginn_models.CollectedData = CollectedData

# Also update sys.modules to use our test models
sys.modules["huginn.core.models"].Base = Base
sys.modules["huginn.core.models"].SpiderRegistry = SpiderRegistry
sys.modules["huginn.core.models"].SpiderRun = SpiderRun
sys.modules["huginn.core.models"].CollectedData = CollectedData

from huginn.core.config import Settings  # noqa: E402

_test_settings = Settings(_env_file=str(_env_test))
DATABASE_URL_SYNC = _test_settings.database_url_sync
DATABASE_URL_ASYNC = _test_settings.database_url


@pytest.fixture(scope="session")
def sync_engine():
    """创建同步 SQLAlchemy Engine（session 级别，整个测试会话共享）"""
    engine = create_engine(DATABASE_URL_SYNC, echo=False)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_engine(_create_tables) -> AsyncEngine:  # noqa: ARG001
    """创建异步 SQLAlchemy Engine（每个测试函数独立）

    注意：依赖 _create_tables fixture 确保表被创建。
    """
    engine = create_async_engine(DATABASE_URL_ASYNC, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def _create_tables(sync_engine):
    """在测试开始时创建所有表，结束时删除

    名称以下划线开头，表示这是一个自动使用的 fixture，
    会被 db_session 和 async_db_session 自动引用。
    """
    import os

    db_path = "test_db.sqlite"

    # Create tables
    Base.metadata.create_all(sync_engine)
    yield
    # Drop tables
    Base.metadata.drop_all(sync_engine)

    # Clean up test database file
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="function")
def db_session(sync_engine, _create_tables) -> Generator[Session, None, None]:
    """为每个测试函数创建独立的数据库会话

    每个测试在事务中运行，测试后回滚，保证测试间隔离
    """
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    # 清理：回滚事务，关闭会话和连接
    session.close()
    transaction.rollback()
    connection.close()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(
    async_engine: AsyncEngine, _create_tables
) -> AsyncGenerator[AsyncSession, None]:
    """为每个异步测试函数创建独立的数据库会话

    注意：不使用事务回滚，让每个测试自己管理事务。
    测试之间通过删除数据来隔离。
    """
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session

    # Clean up: delete all data after test
    async with async_session_maker() as cleanup_session:
        await cleanup_session.run_sync(lambda _: _.execute(CollectedData.__table__.delete()))
        await cleanup_session.run_sync(lambda _: _.execute(SpiderRun.__table__.delete()))
        await cleanup_session.commit()
