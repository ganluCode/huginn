"""FastAPI 依赖注入

提供数据库、Redis 等共享资源的依赖注入函数。
"""

from collections.abc import AsyncGenerator

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.core.config import settings
from huginn.core.db import AsyncSessionLocal

__all__ = ["get_db_session", "get_redis"]

# 模块级 Redis 客户端缓存（全局单例）
_redis_client: Redis | None = None


async def get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """获取异步数据库 session 的依赖注入函数

    通过 FastAPI 的 Depends() 使用，每次请求创建一个新的 session。
    请求结束后自动关闭 session，防止连接泄漏。
    如果数据库连接失败，返回 None（降级处理）。

    Yields:
        AsyncSession | None: SQLAlchemy 异步 session，连接失败时为 None

    Example:
        from fastapi import Depends

        async def my_endpoint(session: AsyncSession = Depends(get_db_session)):
            if session:
                result = await session.execute(...)
    """
    try:
        async with AsyncSessionLocal() as session:
            yield session
            # 退出 context manager 时，session 会自动关闭
    except Exception:
        # 数据库连接失败，yield None 表示降级
        yield None


async def get_redis() -> Redis | None:
    """获取 Redis 客户端的依赖注入函数

    通过 FastAPI 的 Depends() 使用。Redis 不可用时返回 None，不抛出异常。
    使用模块级缓存，避免每次请求都创建新连接。

    Returns:
        Redis | None: Redis 客户端实例，Redis 不可用时返回 None

    Example:
        from fastapi import Depends

        async def my_endpoint(redis: Redis | None = Depends(get_redis)):
            if redis:
                await redis.ping()
            else:
                # Redis 不可用，使用降级逻辑
                ...
    """
    global _redis_client

    # 如果已缓存，直接返回
    if _redis_client is not None:
        return _redis_client

    try:
        # 创建 Redis 客户端
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,  # 5秒超时
            socket_timeout=5,
        )
        # 尝试 ping 验证连接
        _redis_client.ping()
        return _redis_client
    except Exception:
        # Redis 不可用，返回 None（降级）
        _redis_client = None
        return None
