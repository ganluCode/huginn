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

from sqlalchemy import String, cast
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

                # 清理多种可能的密码泄露模式
                import re

                # 模式 1: postgresql://user:password@host:port/db
                # 模式 2: password 'secret123' 或 password="secret123"
                # 模式 3: with password 'secret123'

                # 移除连接字符串中的认证部分
                if "://" in error_msg and "@" in error_msg:
                    # 匹配 protocol://user:password@host
                    error_msg = re.sub(r'(\w+)://\S+?@', r'\1://***@', error_msg)

                # 移除明文密码声明 (password 'xxx' 或 password="xxx")
                error_msg = re.sub(r"password\s*['\"][^'\"]*['\"]", "password '***'", error_msg, flags=re.IGNORECASE)
                error_msg = re.sub(r"with\s+password\s+['\"][^'\"]*['\"]", "with password '***'", error_msg, flags=re.IGNORECASE)

                # 添加统一前缀
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
        from sqlalchemy import and_, or_, select

        async with self._session_factory() as session:
            try:
                # 构建基础查询
                stmt = select(CollectedData)

                # 构建 WHERE 条件
                conditions = []

                if source is not None:
                    conditions.append(CollectedData.source == source)

                if category is not None:
                    conditions.append(CollectedData.category == category)

                if keyword is not None:
                    # 转义 LIKE 特殊字符，防止 SQL 注入
                    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    keyword_pattern = f"%{escaped}%"

                    # data->>'title' ILIKE
                    title_search = CollectedData.data.op("->>")("title").ilike(keyword_pattern)

                    # data::text ILIKE（用 cast 替代已移除的 astext）
                    full_text_search = cast(CollectedData.data, String).ilike(keyword_pattern)

                    conditions.append(or_(title_search, full_text_search))

                if time_from is not None:
                    conditions.append(CollectedData.collected_at >= time_from)

                if time_to is not None:
                    conditions.append(CollectedData.collected_at <= time_to)

                # 应用所有条件
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 排序：按 collected_at DESC
                stmt = stmt.order_by(CollectedData.collected_at.desc())

                # 分页
                stmt = stmt.limit(limit).offset(offset)

                # 执行查询
                result = await session.execute(stmt)
                rows = result.scalars().all()

                # 转换为字典格式
                return [
                    {
                        "id": row.id,
                        "source": row.source,
                        "category": row.category,
                        "collected_at": row.collected_at.isoformat(),
                        "data": row.data,
                    }
                    for row in rows
                ]

            except Exception as e:
                logger.error(f"Failed to query data: {e}")
                raise StorageError(f"Query failed: {str(e)}") from e

    async def get_latest(self, source: str | None = None, n: int = 20) -> list[dict]:
        """获取最新的采集数据

        Args:
            source: 数据源标识，None 表示跨所有数据源
            n: 返回记录数，默认 20

        Returns:
            最新的 n 条数据，按 collected_at 降序排列
        """
        from sqlalchemy import select

        async with self._session_factory() as session:
            try:
                # 构建查询
                stmt = select(CollectedData)

                # 添加 source 过滤条件
                if source is not None:
                    stmt = stmt.where(CollectedData.source == source)

                # 排序：按 collected_at DESC
                stmt = stmt.order_by(CollectedData.collected_at.desc())

                # 限制返回数量
                stmt = stmt.limit(n)

                # 执行查询
                result = await session.execute(stmt)
                rows = result.scalars().all()

                # 转换为字典格式
                return [
                    {
                        "id": row.id,
                        "source": row.source,
                        "category": row.category,
                        "collected_at": row.collected_at.isoformat(),
                        "data": row.data,
                    }
                    for row in rows
                ]

            except Exception as e:
                logger.error(f"Failed to get latest data: {e}")
                raise StorageError(f"Get latest failed: {str(e)}") from e

    async def count(self, source: str | None = None, category: str | None = None) -> int:
        """统计符合条件的记录数

        Args:
            source: 按数据源过滤，None 表示不过滤
            category: 按分类过滤，None 表示不过滤

        Returns:
            符合条件的记录总数
        """
        from sqlalchemy import and_, func, select

        async with self._session_factory() as session:
            try:
                # 构建计数查询
                stmt = select(func.count(CollectedData.id))

                # 构建 WHERE 条件
                conditions = []

                if source is not None:
                    conditions.append(CollectedData.source == source)

                if category is not None:
                    conditions.append(CollectedData.category == category)

                # 应用所有条件
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 执行查询
                result = await session.execute(stmt)
                count_value = result.scalar_one()

                return int(count_value) if count_value is not None else 0

            except Exception as e:
                logger.error(f"Failed to count data: {e}")
                raise StorageError(f"Count failed: {str(e)}") from e
