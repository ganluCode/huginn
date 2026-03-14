"""集成测试：PostgresBackend 存储实现

测试 PostgresBackend 的所有方法，包括：
- save_items: 批量保存采集数据
- query: 按条件查询采集数据
- get_latest: 获取最新数据
- count: 统计记录数
- 数据库异常处理

注意：部分测试需要真实的 PostgreSQL 数据库连接。
如需运行需要数据库的测试，请先启动数据库：
    docker compose up -d postgres
"""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import exc as sqlalchemy_exc
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


class TestPostgresBackendQuery:
    """测试 PostgresBackend.query 方法"""

    @pytest.mark.asyncio
    async def test_query_default_params(self, async_engine):
        """query() 不传参数时返回最多 100 条，按 collected_at DESC 排序"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 先插入测试数据
        items = [{"title": f"Item {i}", "url": f"https://example.com/{i}"} for i in range(5)]
        await backend.save_items("test_query_default", "tech", items)

        # 查询所有数据
        results = await backend.query()

        # 验证结果
        assert len(results) >= 5
        # 验证按 collected_at DESC 排序
        timestamps = [r["collected_at"] for r in results[:5]]
        assert timestamps == sorted(timestamps, reverse=True)

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_query_default'"))

    @pytest.mark.asyncio
    async def test_query_filter_by_source(self, async_engine):
        """query(source='hackernews') 只返回指定 source 的记录"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入不同 source 的数据
        await backend.save_items("hackernews", "tech", [{"title": "HN Item", "url": "https://hn.com"}])
        await backend.save_items("github", "tech", [{"title": "GH Item", "url": "https://github.com"}])

        # 查询指定 source
        results = await backend.query(source="hackernews")

        assert len(results) == 1
        assert results[0]["source"] == "hackernews"
        assert results[0]["data"]["title"] == "HN Item"

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source IN ('hackernews', 'github')"))

    @pytest.mark.asyncio
    async def test_query_filter_by_category(self, async_engine):
        """query(category='tech') 只返回指定 category 的记录"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入不同 category 的数据
        await backend.save_items("test_source", "tech", [{"title": "Tech Item"}])
        await backend.save_items("test_source", "finance", [{"title": "Finance Item"}])

        # 查询指定 category
        results = await backend.query(category="tech")

        assert len(results) >= 1
        assert all(r["category"] == "tech" for r in results)

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_source'"))

    @pytest.mark.asyncio
    async def test_query_keyword_search(self, async_engine):
        """query(keyword='python') 搜索 data->>'title' 和 data::text"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入包含关键词的数据
        await backend.save_items("test_keyword", "tech", [
            {"title": "Python Programming Guide"},
            {"title": "JavaScript Basics"},
            {"description": "Learn python async"},  # title 不包含但 description 包含
            {"content": "No match here"},
        ])

        # 搜索关键词
        results = await backend.query(keyword="python")

        assert len(results) == 2
        titles = [r["data"].get("title", "") for r in results]
        assert "Python Programming Guide" in titles
        assert any("python" in str(r["data"]).lower() for r in results)

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_keyword'"))

    @pytest.mark.asyncio
    async def test_query_keyword_with_special_chars(self, async_engine):
        """query(keyword='%test_') 正确转义特殊字符，防 SQL 注入"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入包含特殊字符的数据
        await backend.save_items("test_special", "tech", [
            {"title": "%test_ pattern"},
            {"title": "normal item"},
        ])

        # 搜索包含特殊字符的模式 - 应该正常工作
        results = await backend.query(keyword="%test_")

        assert len(results) == 1
        assert results[0]["data"]["title"] == "%test_ pattern"

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_special'"))

    @pytest.mark.asyncio
    async def test_query_with_limit_and_offset(self, async_engine):
        """query(limit=5, offset=2) 跳过前 2 条返回第 3-7 条"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入 10 条数据
        items = [{"title": f"Item {i}", "seq": i} for i in range(10)]
        await backend.save_items("test_pagination", "tech", items)

        # 查询 limit=5, offset=2
        results = await backend.query(source="test_pagination", limit=5, offset=2)

        assert len(results) == 5

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_pagination'"))

    @pytest.mark.asyncio
    async def test_query_with_time_range(self, async_engine):
        """query(time_from, time_to) 只返回指定时间范围内的记录"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入测试数据
        await backend.save_items("test_time", "tech", [{"title": "Time Item"}])

        # 获取当前时间
        from datetime import datetime, timedelta
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_hour_later = now + timedelta(hours=1)

        # 查询时间范围内的数据
        results = await backend.query(
            source="test_time",
            time_from=one_hour_ago,
            time_to=one_hour_later,
        )

        assert len(results) >= 1
        assert all(r["source"] == "test_time" for r in results)

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_time'"))

    @pytest.mark.asyncio
    async def test_query_return_format(self, async_engine):
        """返回每条 dict 含正确字段：id, source, category, collected_at, data"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 插入测试数据
        await backend.save_items("test_format", "tech", [{"title": "Format Test", "value": 42}])

        # 查询数据
        results = await backend.query(source="test_format")

        assert len(results) >= 1
        result = results[0]

        # 验证字段存在且类型正确
        assert isinstance(result["id"], int)
        assert isinstance(result["source"], str)
        assert isinstance(result["category"], str)
        assert isinstance(result["collected_at"], str)
        # collected_at 应该是 ISO 格式
        assert "T" in result["collected_at"]
        assert isinstance(result["data"], dict)
        assert result["data"]["title"] == "Format Test"
        assert result["data"]["value"] == 42

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_format'"))


class TestPostgresBackendQueryMocked:
    """使用 mock 测试 PostgresBackend.query 方法（无需真实数据库）"""

    @pytest.mark.asyncio
    async def test_query_empty_result(self):
        """当查询返回空结果时，应返回空列表"""
        backend = PostgresBackend()

        # Mock session 和查询结果
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_session.execute.return_value = mock_result

        # Mock session_factory
        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            results = await backend.query()

            assert results == []

    @pytest.mark.asyncio
    async def test_query_converts_rows_to_dict(self):
        """测试查询结果正确转换为字典格式"""
        backend = PostgresBackend()

        # 创建 mock 数据行
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.source = "test_source"
        mock_row.category = "tech"
        mock_row.data = {"title": "Test", "value": 42}
        # 模拟 datetime 的 isoformat 方法
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2024-03-14T12:00:00"
        mock_row.collected_at = mock_dt

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            results = await backend.query()

            assert len(results) == 1
            assert results[0]["id"] == 1
            assert results[0]["source"] == "test_source"
            assert results[0]["category"] == "tech"
            assert results[0]["collected_at"] == "2024-03-14T12:00:00"
            assert results[0]["data"]["title"] == "Test"
            assert results[0]["data"]["value"] == 42

    @pytest.mark.asyncio
    async def test_query_handles_exceptions(self):
        """当查询抛出异常时，应转换为 StorageError"""
        backend = PostgresBackend()

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection lost")

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            with pytest.raises(StorageError) as exc_info:
                await backend.query()

            assert "Query failed" in str(exc_info.value)


class TestPostgresBackendGetLatest:
    """测试 PostgresBackend.get_latest 方法"""

    @pytest.mark.asyncio
    async def test_get_latest_default_returns_twenty(self, async_engine):
        """get_latest() 不传参时应返回最新 20 条"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入 25 条数据
        items = [{"title": f"Item {i}", "order": i} for i in range(25)]
        await backend.save_items("test_get_latest", "tech", items)

        # 查询最新 20 条
        results = await backend.get_latest()

        assert len(results) == 20

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_get_latest'"))

    @pytest.mark.asyncio
    async def test_get_latest_with_source_filter(self, async_engine):
        """get_latest(source='hackernews', n=5) 应返回最多 5 条指定 source 的数据"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入不同 source 的数据
        await backend.save_items("source_a", "tech", [{"title": "A1"}])
        await backend.save_items("source_b", "tech", [{"title": "B1"}])
        await backend.save_items("source_a", "tech", [{"title": "A2"}])
        await backend.save_items("source_a", "tech", [{"title": "A3"}])

        # 查询 source_a 的最新 2 条
        results = await backend.get_latest(source="source_a", n=2)

        assert len(results) == 2
        assert all(r["source"] == "source_a" for r in results)

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source IN ('source_a', 'source_b')"))

    @pytest.mark.asyncio
    async def test_get_latest_returns_desc_order(self, async_engine):
        """get_latest 返回结果应按 collected_at DESC 排序"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入数据（会有时间差异）
        import asyncio
        for i in range(5):
            await backend.save_items("test_order", "tech", [{"title": f"Item {i}", "seq": i}])
            await asyncio.sleep(0.01)  # 确保时间差异

        # 查询最新 5 条
        results = await backend.get_latest(source="test_order", n=5)

        # 验证排序（按 collected_at DESC）
        times = [r["collected_at"] for r in results]
        assert times == sorted(times, reverse=True), "Results should be ordered by collected_at DESC"

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_order'"))

    @pytest.mark.asyncio
    async def test_get_latest_cross_source(self, async_engine):
        """get_latest(source=None, n=10) 应跨所有 source 返回最新 10 条"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入多个 source 的数据
        await backend.save_items("source_a", "tech", [{"title": "A1"}])
        await backend.save_items("source_b", "tech", [{"title": "B1"}])
        await backend.save_items("source_c", "social", [{"title": "C1"}])

        # 跨 source 查询
        results = await backend.get_latest(source=None, n=10)
        sources = {r["source"] for r in results}

        assert "source_a" in sources
        assert "source_b" in sources
        assert "source_c" in sources

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source IN ('source_a', 'source_b', 'source_c')"))


class TestPostgresBackendCount:
    """测试 PostgresBackend.count 方法"""

    @pytest.mark.asyncio
    async def test_count_returns_total_rows(self, async_engine):
        """count() 应返回 collected_data 表总行数"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入数据前计数
        before = await backend.count()

        # 写入 5 条
        await backend.save_items("test_count", "tech", [
            {"title": f"Item {i}"} for i in range(5)
        ])

        # 写入后计数
        after = await backend.count()
        assert after == before + 5

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_count'"))

    @pytest.mark.asyncio
    async def test_count_with_source_filter(self, async_engine):
        """count(source='hackernews') 应只统计指定 source 的行数"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入不同 source 的数据
        await backend.save_items("source_a", "tech", [{"title": "A1"}])
        await backend.save_items("source_a", "tech", [{"title": "A2"}])
        await backend.save_items("source_b", "tech", [{"title": "B1"}])

        assert await backend.count(source="source_a") == 2
        assert await backend.count(source="source_b") == 1

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source IN ('source_a', 'source_b')"))

    @pytest.mark.asyncio
    async def test_count_with_category_filter(self, async_engine):
        """count(category='tech') 应只统计指定 category 的行数"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入不同 category 的数据
        await backend.save_items("test_source", "tech", [{"title": "T1"}])
        await backend.save_items("test_source", "tech", [{"title": "T2"}])
        await backend.save_items("test_source", "social", [{"title": "S1"}])

        assert await backend.count(category="tech") == 2
        assert await backend.count(category="social") == 1

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_source'"))

    @pytest.mark.asyncio
    async def test_count_with_combined_filters(self, async_engine):
        """count(source, category) 应同时过滤两个条件"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 写入不同组合的数据
        await backend.save_items("source_a", "tech", [{"title": "AT1"}])
        await backend.save_items("source_a", "tech", [{"title": "AT2"}])
        await backend.save_items("source_a", "social", [{"title": "AS1"}])
        await backend.save_items("source_b", "tech", [{"title": "BT1"}])

        # 组合查询
        assert await backend.count(source="source_a", category="tech") == 2
        assert await backend.count(source="source_a", category="social") == 1
        assert await backend.count(source="source_b", category="tech") == 1

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source IN ('source_a', 'source_b')"))


class TestPostgresBackendSaveItemsIntegration:
    """测试 save_items 与其他方法的集成"""

    @pytest.mark.asyncio
    async def test_save_items_increases_count(self, async_engine):
        """save_items 写入 N 条后 count() 应增加 N"""
        if not await check_db_available(async_engine):
            pytest.skip("Database not available")

        backend = PostgresBackend(engine=async_engine)

        # 获取初始计数
        initial_count = await backend.count(source="test_integration")

        # 写入 3 条数据
        items = [
            {"title": f"Item {i}", "score": i * 10, "url": f"http://example.com/{i}"}
            for i in range(3)
        ]
        saved_count = await backend.save_items("test_integration", "tech", items)

        # 验证保存数量
        assert saved_count == 3

        # 验证 count 增加
        final_count = await backend.count(source="test_integration")
        assert final_count == initial_count + 3

        # 清理
        async with async_engine.begin() as conn:
            await conn.execute(text("DELETE FROM collected_data WHERE source = 'test_integration'"))


class TestPostgresBackendExceptionHandlingMocked:
    """使用 mock 测试 PostgresBackend 的异常处理（无需真实数据库）"""

    @pytest.mark.asyncio
    async def test_database_error_raises_storage_error(self):
        """数据库异常时 save_items 应抛出 StorageError"""
        backend = PostgresBackend()

        # Mock session.execute 抛出数据库异常
        mock_session = AsyncMock()
        mock_session.execute.side_effect = sqlalchemy_exc.DBAPIError("Connection failed", {}, None)

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            with pytest.raises(StorageError) as exc_info:
                await backend.save_items("test", "tech", [{"title": "Test"}])

            # 验证异常类型
            assert isinstance(exc_info.value, StorageError)
            assert "Database error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_storage_error_hides_password(self):
        """StorageError 信息不应包含数据库密码"""
        backend = PostgresBackend()

        # Mock session 抛出包含密码的异常
        error_msg = "connection to server at \"localhost\", port 5432 failed: FATAL: password authentication failed for user 'huginn' with password 'secret123'"
        mock_session = AsyncMock()
        mock_session.execute.side_effect = sqlalchemy_exc.DBAPIError(error_msg, {}, Exception())

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            with pytest.raises(StorageError) as exc_info:
                await backend.save_items("test", "tech", [{"title": "Test"}])

            # 验证错误信息不包含密码
            error_message = str(exc_info.value)
            assert "secret123" not in error_message
            # 不应该有明文 password 字段出现
            assert "password 'secret123'" not in error_message
            assert "password=secret123" not in error_message

    @pytest.mark.asyncio
    async def test_storage_error_hides_connection_string(self):
        """StorageError 信息应隐藏连接字符串中的密码"""
        backend = PostgresBackend()

        # Mock session 抛出包含连接字符串的异常
        error_msg = "could not connect to server: Connection refused postgresql://huginn:my_secret_pass@localhost:5432/db"
        mock_session = AsyncMock()
        mock_session.execute.side_effect = sqlalchemy_exc.DBAPIError(error_msg, {}, Exception())

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            with pytest.raises(StorageError) as exc_info:
                await backend.save_items("test", "tech", [{"title": "Test"}])

            # 验证错误信息不包含敏感的密码部分
            error_message = str(exc_info.value)
            assert "my_secret_pass" not in error_message
            # 密码应该被替换为 ***
            assert "***" in error_message
            # 不应该包含完整的用户名:密码组合
            assert "huginn:my_secret_pass@" not in error_message
            # 可以保留主机名和端口（这些不是敏感信息）
            assert "localhost:5432" in error_message

    @pytest.mark.asyncio
    async def test_storage_error_preserves_error_context(self):
        """StorageError 应保留原始错误作为 cause"""
        backend = PostgresBackend()

        # 创建一个自定义数据库异常
        original_error = sqlalchemy_exc.DBAPIError("Table doesn't exist", {}, None)
        mock_session = AsyncMock()
        mock_session.execute.side_effect = original_error

        with patch.object(backend, "_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            with pytest.raises(StorageError) as exc_info:
                await backend.save_items("test", "tech", [{"title": "Test"}])

            # 验证原始错误被保留为 cause
            assert exc_info.value.__cause__ is original_error
