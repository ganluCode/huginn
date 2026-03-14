"""Pytest 配置和共享 fixtures"""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

# 加载 .env.test 配置（在导入 huginn 模块之前）
_env_test = Path(__file__).resolve().parent.parent / ".env.test"
load_dotenv(_env_test, override=True)

from huginn.core.config import Settings  # noqa: E402
from huginn.core.models import Base  # noqa: E402

# 用 .env.test 重新构建配置
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
async def async_engine(_create_tables) -> AsyncEngine:  # noqa: ARG001 (unused argument is fine, it's a fixture)
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
    Base.metadata.create_all(sync_engine)
    yield
    Base.metadata.drop_all(sync_engine)


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

    每个测试在事务中运行，测试后回滚，保证测试间隔离
    """
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session, session.begin():
        yield session

        # 测试结束后自动回滚（pytest-asyncio 会处理）
