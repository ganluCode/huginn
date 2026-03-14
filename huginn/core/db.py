"""数据库连接管理

配置异步（asyncpg）和同步（psycopg2）两套 SQLAlchemy 2.0 引擎及 session 工厂。
"""

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from huginn.core.config import settings

# 异步引擎：使用 asyncpg 驱动
async_engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)


# 异步 session 工厂
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 同步引擎：使用 psycopg2 驱动
sync_engine = create_engine(
    settings.database_url_sync,
)


# 同步 session 工厂
SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    class_=Session,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """创建异步 session 的生成器

    用于依赖注入，每次调用返回一个新的 session。

    Yields:
        AsyncSession: SQLAlchemy 异步 session

    Example:
        async for session in get_async_session():
            # 使用 session 进行数据库操作
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
