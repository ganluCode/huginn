"""存储层抽象接口

定义了 StorageBackend Protocol，用于抽象不同的存储实现。
目前只规划了 PostgresBackend，但保留扩展性以支持其他存储后端（如 ClickHouse、文件系统等）。

设计原则：
- 使用 Protocol 而非 ABC：不强制继承，实现同样方法即可
- 结构子类型：只要实现了相同方法，即视为符合协议
- 薄抽象：只定义必要的方法，不做额外封装
"""

import logging
from datetime import datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from huginn.core.db import async_engine
from huginn.core.exceptions import StorageError
from huginn.core.models import CollectedData

logger = logging.getLogger(__name__)


@runtime_checkable
class StorageBackend(Protocol):
    """存储后端接口

    使用 typing.Protocol 定义存储后端接口，任何实现了这些方法的类
    都被视为 StorageBackend（结构子类型）。

    方法说明：
        save_items: 批量保存采集数据，返回成功保存的条数
        query: 按条件查询采集数据，支持多条件过滤和分页
        get_latest: 获取最新的 N 条数据
        count: 统计符合条件的记录数
    """

    async def save_items(self, source: str, category: str, items: list[dict]) -> int:
        """批量保存采集数据

        Args:
            source: 数据源标识（如 "hackernews", "weibo_hot"）
            category: 数据分类（tech/social/finance/market/news）
            items: 待保存的数据列表，每项为一个字典

        Returns:
            成功保存的数据条数

        Raises:
            StorageError: 存储操作失败时抛出
        """
        ...

    async def query(
        self,
        source: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """按条件查询采集数据

        Args:
            source: 按数据源过滤，None 表示不过滤
            category: 按分类过滤，None 表示不过滤
            keyword: 关键词搜索（在 data 字段中搜索），None 表示不过滤
            time_from: 起始时间（包含），None 表示不限制起始时间
            time_to: 结束时间（包含），None 表示不限制结束时间
            limit: 返回结果的最大数量，默认 100
            offset: 跳过的记录数，用于分页，默认 0

        Returns:
            查询结果列表，每项包含 id、source、category、collected_at、data 字段
        """
        ...

    async def get_latest(self, source: str | None = None, n: int = 20) -> list[dict]:
        """获取最新的采集数据

        Args:
            source: 数据源标识，None 表示跨所有数据源
            n: 返回记录数，默认 20

        Returns:
            最新的 n 条数据，按 collected_at 降序排列
        """
        ...

    async def count(self, source: str | None = None, category: str | None = None) -> int:
        """统计符合条件的记录数

        Args:
            source: 按数据源过滤，None 表示不过滤
            category: 按分类过滤，None 表示不过滤

        Returns:
            符合条件的记录总数
        """
        ...


class PostgresBackend:
    """PostgreSQL + JSONB 存储后端实现

    实现了 StorageBackend Protocol，提供：
    - 批量数据保存（使用 PostgreSQL INSERT ... VALUES 多值语法）
    - 灵活的 JSONB 字段查询
    - 异常处理和错误日志

    所有方法使用异步 session，适合高并发场景。

    Args:
        engine: 异步 SQLAlchemy 引擎，用于测试注入。默认使用 huginn.core.db.async_engine。
    """

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        """初始化 PostgresBackend

        Args:
            engine: 可选的异步引擎，用于测试。默认使用 huginn.core.db.async_engine。
        """
        self._engine = engine or async_engine
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def save_items(self, source: str, category: str, items: list[dict]) -> int:
        """批量保存采集数据到 PostgreSQL

        使用 PostgreSQL 的 INSERT ... VALUES (...), (...), ... 语法批量插入，
        比逐条 INSERT 性能更高。

        Args:
            source: 数据源标识（如 "hackernews", "weibo_hot"）
            category: 数据分类（tech/social/finance/market/news）
            items: 待保存的数据列表，每项为一个字典

        Returns:
            成功保存的数据条数

        Raises:
            StorageError: 数据库操作失败时抛出，错误信息不包含敏感信息
        """
        if not items:
            return 0

        async with self._session_factory() as session:
            try:
                # 构建批量插入数据
                records = [
                    {
                        "source": source,
                        "category": category,
                        "data": item,
                        "collected_at": datetime.now(),
                    }
                    for item in items
                ]

                # 使用 PostgreSQL 的 executemany 批量插入
                # SQLAlchemy 会将其转换为 INSERT ... VALUES (...), (...) 语法
                await session.execute(
                    pg_insert(CollectedData).returning(CollectedData.id),
                    records,
                )
                await session.commit()

                logger.info(f"Saved {len(items)} items for source={source}")
                return len(items)

            except Exception as e:
                await session.rollback()
                # 清理错误消息，移除可能的敏感信息（如数据库密码）
                error_msg = str(e)
                # 移除包含密码的连接字符串片段
                if "://" in error_msg:
                    # 简单清理：移除协议和认证部分
                    cleaned_msg = error_msg.split("://")[-1].split("@")[-1] if "@" in error_msg else error_msg
                    error_msg = f"Database error: {cleaned_msg}"
                else:
                    error_msg = f"Database error: {error_msg}"

                logger.error(f"Failed to save items for source={source}: {error_msg}")
                raise StorageError(error_msg) from e

    async def query(
        self,
        source: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """按条件查询采集数据

        Args:
            source: 按数据源过滤，None 表示不过滤
            category: 按分类过滤，None 表示不过滤
            keyword: 关键词搜索（在 data 字段中搜索），None 表示不过滤
            time_from: 起始时间（包含），None 表示不限制起始时间
            time_to: 结束时间（包含），None 表示不限制结束时间
            limit: 返回结果的最大数量，默认 100
            offset: 跳过的记录数，用于分页，默认 0

        Returns:
            查询结果列表，每项包含 id、source、category、collected_at、data 字段
        """
        # TODO: 在 F-007 中实现
        raise NotImplementedError("query method will be implemented in F-007")

    async def get_latest(self, source: str | None = None, n: int = 20) -> list[dict]:
        """获取最新的采集数据

        Args:
            source: 数据源标识，None 表示跨所有数据源
            n: 返回记录数，默认 20

        Returns:
            最新的 n 条数据，按 collected_at 降序排列
        """
        # TODO: 在 F-008 中实现
        raise NotImplementedError("get_latest method will be implemented in F-008")

    async def count(self, source: str | None = None, category: str | None = None) -> int:
        """统计符合条件的记录数

        Args:
            source: 按数据源过滤，None 表示不过滤
            category: 按分类过滤，None 表示不过滤

        Returns:
            符合条件的记录总数
        """
        # TODO: 在 F-008 中实现
        raise NotImplementedError("count method will be implemented in F-008")
