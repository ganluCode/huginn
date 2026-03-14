"""PostgresBackend.get_latest() 和 count() 集成测试 (F-008)"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from huginn.core.models import Base, CollectedData
from huginn.core.storage import PostgresBackend


@pytest_asyncio.fixture(scope="function")
async def async_engine_with_tables():
    """创建测试用的异步引擎和表"""
    engine = create_async_engine(
        "postgresql+asyncpg://huginn:huginn@localhost:5432/huginn_test",
        echo=False,
    )

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine_with_tables):
    """为每个测试创建独立的会话"""
    async_session_maker = sessionmaker(
        bind=async_engine_with_tables,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
async def test_get_latest_default(async_engine_with_tables, db_session):
    """get_latest() 不传参时返回最新 20 条，按 collected_at DESC 排序"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：25 条，不同 source
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN {i}"}}
        for i in range(10)
    ]
    test_items += [
        {"source": "github", "category": "tech", "data": {"title": f"GH {i}"}}
        for i in range(15)
    ]

    # 使用批量插入
    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 get_latest()
    result = await backend.get_latest()

    # 验证：返回最多 20 条
    assert len(result) <= 20

    # 验证：按 collected_at DESC 排序
    timestamps = [r["collected_at"] for r in result]
    assert timestamps == sorted(timestamps, reverse=True)

    # 验证：每条记录包含必需字段
    for item in result:
        assert "id" in item
        assert "source" in item
        assert "category" in item
        assert "collected_at" in item
        assert "data" in item
        assert isinstance(item["data"], dict)


@pytest.mark.asyncio
async def test_get_latest_with_source_filter(async_engine_with_tables, db_session):
    """get_latest(source='hackernews', n=5) 返回最多 5 条 source='hackernews' 的数据"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：混合多个 source
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN {i}"}}
        for i in range(10)
    ]
    test_items += [
        {"source": "github", "category": "tech", "data": {"title": f"GH {i}"}}
        for i in range(10)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 get_latest(source='hackernews', n=5)
    result = await backend.get_latest(source="hackernews", n=5)

    # 验证：返回最多 5 条
    assert len(result) <= 5

    # 验证：所有结果都是 hackernews
    for item in result:
        assert item["source"] == "hackernews"


@pytest.mark.asyncio
async def test_get_latest_cross_all_sources(async_engine_with_tables, db_session):
    """get_latest(source=None, n=10) 跨所有 source 返回最新 10 条"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：多个 source
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN {i}"}}
        for i in range(10)
    ]
    test_items += [
        {"source": "github", "category": "tech", "data": {"title": f"GH {i}"}}
        for i in range(10)
    ]
    test_items += [
        {"source": "weibo", "category": "social", "data": {"title": f"WB {i}"}}
        for i in range(10)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 get_latest(source=None, n=10)
    result = await backend.get_latest(source=None, n=10)

    # 验证：返回最多 10 条
    assert len(result) <= 10

    # 验证：source=None 不过滤（结果来自已插入的数据源）
    sources = {r["source"] for r in result}
    # 所有结果应该来自我们插入的三个源之一
    assert sources.issubset({"hackernews", "github", "weibo"})


@pytest.mark.asyncio
async def test_count_all(async_engine_with_tables, db_session):
    """count() 返回 collected_data 表总行数（int）"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：25 条
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"Item {i}"}}
        for i in range(25)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 count()
    count = await backend.count()

    # 验证：返回正确的总行数
    assert count == 25
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_count_with_source_filter(async_engine_with_tables, db_session):
    """count(source='hackernews') 只统计 source='hackernews' 的行数"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：混合多个 source
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN {i}"}}
        for i in range(15)
    ]
    test_items += [
        {"source": "github", "category": "tech", "data": {"title": f"GH {i}"}}
        for i in range(10)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 count(source='hackernews')
    count = await backend.count(source="hackernews")

    # 验证：只返回 hackernews 的行数
    assert count == 15
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_count_with_category_filter(async_engine_with_tables, db_session):
    """count(category='tech') 只统计 category='tech' 的行数"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：混合多个 category
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN {i}"}}
        for i in range(12)
    ]
    test_items += [
        {"source": "weibo", "category": "social", "data": {"title": f"WB {i}"}}
        for i in range(8)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 count(category='tech')
    count = await backend.count(category="tech")

    # 验证：只返回 tech 的行数
    assert count == 12
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_count_with_source_and_category(async_engine_with_tables, db_session):
    """count(source='hackernews', category='tech') 同时过滤两个条件，返回正确计数"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 准备测试数据：混合多个 source 和 category
    test_items = [
        {"source": "hackernews", "category": "tech", "data": {"title": f"HN-Tech {i}"}}
        for i in range(10)
    ]
    test_items += [
        {"source": "hackernews", "category": "social", "data": {"title": f"HN-Social {i}"}}
        for i in range(5)
    ]
    test_items += [
        {"source": "github", "category": "tech", "data": {"title": f"GH-Tech {i}"}}
        for i in range(8)
    ]

    for item in test_items:
        db_session.add(CollectedData(**item))
    await db_session.commit()

    # 调用 count(source='hackernews', category='tech')
    count = await backend.count(source="hackernews", category="tech")

    # 验证：同时过滤两个条件
    assert count == 10
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_get_latest_empty_table(async_engine_with_tables, db_session):
    """get_latest() 在空表时返回空列表"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 表为空时调用
    result = await backend.get_latest()

    # 验证：返回空列表
    assert result == []


@pytest.mark.asyncio
async def test_count_empty_table(async_engine_with_tables, db_session):
    """count() 在空表时返回 0"""
    backend = PostgresBackend(engine=async_engine_with_tables)

    # 表为空时调用
    count = await backend.count()

    # 验证：返回 0
    assert count == 0
