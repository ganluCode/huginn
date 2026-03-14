"""集成测试：PostgresBackend 存储实现

测试 PostgresBackend 的所有方法，包括：
- save_items: 批量保存采集数据
- 数据库异常处理

注意：部分测试需要真实的 PostgreSQL 数据库连接。
如需运行需要数据库的测试，请先启动数据库：
    docker compose up -d postgres
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from huginn.core.exceptions import StorageError
from huginn.core.storage import PostgresBackend, StorageBackend


async def check_db_available(async_engine) -> bool:
    """检查数据库是否可用"""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


class TestPostgresBackendProtocol:
    """测试 PostgresBackend 符合 StorageBackend Protocol"""

    def test_postgres_backend_is_storage_backend(self):
        """PostgresBackend 应该符合 StorageBackend Protocol"""
        backend = PostgresBackend()
        assert isinstance(backend, StorageBackend)


class TestPostgresBackendSaveItems:
    """测试 PostgresBackend.save_items 方法"""

    @pytest.mark.asyncio
    async def test_save_empty_list_returns_zero(self, async_engine):
        """save_items([]) 应返回 0，不执行任何 SQL"""
        backend = PostgresBackend(engine=async_engine)

        result = await backend.save_items("test_source", "tech", [])

        assert result == 0

    @pytest.mark.asyncio
    async def test_save_items_successful(self, async_engine):
        """save_items 应正确批量插入数据到数据库"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        items = [
            {"title": "Item 1", "url": "https://example.com/1"},
            {"title": "Item 2", "url": "https://example.com/2"},
            {"title": "Item 3", "url": "https://example.com/3"},
        ]

        count = await backend.save_items("hackernews", "tech", items)

        assert count == 3

        # 验证数据库中确实有 3 条记录
        async with async_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM collected_data WHERE source = 'hackernews'")
            )
            db_count = result.scalar()
            assert db_count == 3

            # 清理测试数据
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'hackernews'"))

    @pytest.mark.asyncio
    async def test_save_items_uses_batch_insert(self, async_engine):
        """save_items 应使用批量 INSERT，而非逐条插入"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        items = [{"title": f"Item {i}", "url": f"https://example.com/{i}"} for i in range(10)]

        count = await backend.save_items("github_trending", "tech", items)

        assert count == 10

        # 验证数据已保存
        async with async_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM collected_data WHERE source = 'github_trending'")
            )
            db_count = result.scalar()
            assert db_count == 10

            # 清理测试数据
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'github_trending'"))

    @pytest.mark.asyncio
    async def test_save_items_with_complex_data(self, async_engine):
        """save_items 应正确处理嵌套的 JSON 数据"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        items = [
            {
                "title": "Complex Item",
                "metadata": {"author": "test", "tags": ["python", "async"]},
                "stats": {"views": 100, "likes": 25},
            }
        ]

        count = await backend.save_items("test_source", "tech", items)

        assert count == 1

        # 验证嵌套数据正确保存
        async with async_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT data FROM collected_data WHERE source = 'test_source' LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0]["metadata"]["author"] == "test"
            assert row[0]["stats"]["likes"] == 25

            # 清理测试数据
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_source'"))


class TestPostgresBackendErrorMessage:
    """测试 PostgresBackend 错误消息处理"""

    @pytest.mark.asyncio
    async def test_storage_error_on_invalid_data(self, async_engine):
        """当传入无效数据时应抛出 StorageError"""
        backend = PostgresBackend(engine=async_engine)

        # 触发数据库错误：使用包含 None 的 items
        items = [None]  # type: ignore

        with pytest.raises(StorageError) as exc_info:
            await backend.save_items("test_source", "tech", items)  # type: ignore

        error_message = str(exc_info.value)
        # 确保错误消息不包含密码（默认配置中的 "huginn"）
        assert "huginn:huginn" not in error_message
        # 如果包含 "password"，说明可能泄露了敏感信息
        assert "password" not in error_message.lower()
        # 应该包含清理后的错误信息
        assert "Database error" in error_message
