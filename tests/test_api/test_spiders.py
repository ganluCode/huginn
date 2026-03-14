"""Spider 管理 API 测试

测试 Spider 列表、详情、触发运行等接口。
"""

from collections.abc import AsyncGenerator, Generator, Callable
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from huginn.api.main import app
from huginn.api.deps import get_db_session
from huginn.core.models import SpiderRegistry


@pytest_asyncio.fixture
async def test_session_maker(async_engine):
    """创建测试用的 session maker"""
    return async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def test_session(test_session_maker):
    """为每个测试创建独立的会话，测试后回滚"""
    async with test_session_maker() as session:
        # 使用嵌套事务（SAVEPOINT），确保测试后回滚
        async with session.begin_nested():
            yield session
        # 外层事务会回滚所有更改


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """创建异步测试客户端

    使用测试的 test_session 覆盖 get_db_session 依赖。
    """
    # 覆盖 get_db_session 依赖
    async def override_get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
        yield test_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    # 清理依赖覆盖
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_spiders(test_session: AsyncSession) -> list[SpiderRegistry]:
    """创建测试用的 Spider 数据

    返回 3 个 Spider：
    - hackernews: tech, enabled=True
    - github_trending: tech, enabled=False
    - crypto_price: finance, enabled=True
    """
    now = datetime.now(timezone.utc)

    spiders = [
        SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            config={"url": "https://hacker-news.firebaseio.com/v0/topstories.json"},
            last_run_at=now,
            last_status="success",
            item_count=30,
            created_at=now,
        ),
        SpiderRegistry(
            name="github_trending",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=False,
            config={"url": "https://github.com/trending"},
            last_run_at=now,
            last_status="success",
            item_count=25,
            created_at=now,
        ),
        SpiderRegistry(
            name="crypto_price",
            engine="scrapy",
            category="finance",
            schedule="*/30 * * * *",
            enabled=True,
            config={"api": "coingecko"},
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        ),
    ]

    test_session.add_all(spiders)
    # 不显式 commit，让 fixture 的自动回滚处理清理
    await test_session.flush()

    return spiders


class TestSpiderListEndpoint:
    """测试 GET /api/spiders 端点"""

    @pytest.mark.asyncio
    async def test_spider_list_returns_200_with_items_and_total(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders 返回 200，body 含 items 数组和 total 整数"""
        response = await client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_spider_list_filter_by_category(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?category=tech 只返回 category=tech 的 Spider"""
        response = await client.get("/api/spiders?category=tech")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        # 验证所有返回的 Spider category 都是 tech
        for spider in data["items"]:
            assert spider["category"] == "tech"

    @pytest.mark.asyncio
    async def test_spider_list_filter_by_enabled_true(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?enabled=true 只返回 enabled=true 的 Spider"""
        response = await client.get("/api/spiders?enabled=true")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        # 验证所有返回的 Spider enabled 都是 True
        for spider in data["items"]:
            assert spider["enabled"] is True

    @pytest.mark.asyncio
    async def test_spider_list_filter_by_enabled_false(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?enabled=false 只返回 enabled=false 的 Spider"""
        response = await client.get("/api/spiders?enabled=false")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        # 验证返回的 Spider enabled 是 False
        assert data["items"][0]["enabled"] is False

    @pytest.mark.asyncio
    async def test_spider_list_no_filters_returns_all(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """不传参数时返回所有 Spider"""
        response = await client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_spider_list_ordered_by_created_at_desc(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        """items 按 created_at DESC 排序"""
        now = datetime.now(timezone.utc)

        # 创建 3 个不同 created_at 的 Spider
        spider1 = SpiderRegistry(
            name="spider1",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now.replace(microsecond=100000),
        )
        spider2 = SpiderRegistry(
            name="spider2",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now.replace(microsecond=300000),
        )
        spider3 = SpiderRegistry(
            name="spider3",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now.replace(microsecond=200000),
        )

        test_session.add_all([spider1, spider2, spider3])
        await test_session.flush()

        response = await client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        items = data["items"]
        # 验证顺序：spider2 (300000) > spider3 (200000) > spider1 (100000)
        assert items[0]["name"] == "spider2"
        assert items[1]["name"] == "spider3"
        assert items[2]["name"] == "spider1"

    @pytest.mark.asyncio
    async def test_spider_list_response_structure(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """验证响应包含 SpiderItem 的所有必需字段"""
        response = await client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        spider = data["items"][0]

        # 验证所有必需字段存在
        assert "name" in spider
        assert "engine" in spider
        assert "category" in spider
        assert "schedule" in spider
        assert "enabled" in spider
        assert "last_run_at" in spider
        assert "last_status" in spider
        assert "item_count" in spider
        assert "created_at" in spider

    @pytest.mark.asyncio
    async def test_spider_list_empty_database(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        """数据库为空时返回空列表"""
        response = await client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0


class TestSpiderDetailEndpoint:
    """测试 GET /api/spiders/{name} 端点"""

    @pytest.mark.asyncio
    async def test_spider_detail_returns_200_with_config(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders/hackernews 返回 200，body 含 config 字段"""
        response = await client.get("/api/spiders/hackernews")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # 验证包含 SpiderDetail 的所有字段（包括 config）
        assert "name" in data
        assert data["name"] == "hackernews"
        assert "config" in data
        assert data["config"] == {"url": "https://hacker-news.firebaseio.com/v0/topstories.json"}
        # 验证其他基本字段
        assert "engine" in data
        assert "category" in data
        assert "schedule" in data
        assert "enabled" in data
        assert "last_run_at" in data
        assert "last_status" in data
        assert "item_count" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_spider_detail_not_found_returns_404(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders/nonexistent 返回 404"""
        response = await client.get("/api/spiders/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Spider 'nonexistent' not found"

    @pytest.mark.asyncio
    async def test_spider_detail_datetime_format_utc(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """响应中 last_run_at 为 ISO 8601 UTC 格式（带 Z 后缀）或 null"""
        response = await client.get("/api/spiders/hackernews")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # last_run_at 应该是 ISO 8601 UTC 格式（带 Z 后缀）
        last_run_at = data.get("last_run_at")
        if last_run_at is not None:
            assert isinstance(last_run_at, str)
            assert last_run_at.endswith("Z")

        # created_at 也应该是 ISO 8601 UTC 格式
        created_at = data.get("created_at")
        assert isinstance(created_at, str)
        assert created_at.endswith("Z")

    @pytest.mark.asyncio
    async def test_spider_detail_all_fields_present(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry]
    ):
        """验证 SpiderDetail 包含所有必需字段"""
        response = await client.get("/api/spiders/github_trending")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # 验证 SpiderItem 的所有字段
        assert data["name"] == "github_trending"
        assert data["engine"] == "scrapy"
        assert data["category"] == "tech"
        assert data["schedule"] == "0 */6 * * *"
        assert data["enabled"] is False
        assert "last_run_at" in data
        assert data["last_status"] == "success"
        assert data["item_count"] == 25
        assert "created_at" in data
        # 验证 SpiderDetail 特有的 config 字段
        assert "config" in data
        assert data["config"] == {"url": "https://github.com/trending"}

    @pytest.mark.asyncio
    async def test_spider_detail_null_config(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        """测试 config 为 null 的情况"""
        # 创建一个 config 为 None 的 Spider
        spider = SpiderRegistry(
            name="no_config_spider",
            engine="scrapy",
            category="test",
            enabled=True,
            config=None,
        )
        test_session.add(spider)
        await test_session.flush()

        response = await client.get("/api/spiders/no_config_spider")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["config"] is None


class TestSpiderRunEndpoint:
    """测试 POST /api/spiders/{name}/run 端点"""

    @pytest.mark.asyncio
    async def test_trigger_spider_run_returns_202_with_message_and_run_id(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], test_session: AsyncSession, mocker
    ):
        """POST /api/spiders/hackernews/run 返回 202，body 含 message 和 run_id"""
        # Mock subprocess.Popen 避免真的启动 Scrapy 进程
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        response = await client.post("/api/spiders/hackernews/run")
        assert response.status_code == status.HTTP_202_ACCEPTED

        data = response.json()
        assert "message" in data
        assert "run_id" in data
        assert isinstance(data["run_id"], int)
        assert "hackernews" in data["message"]

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_spider_returns_404(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], mocker
    ):
        """POST /api/spiders/nonexistent/run 返回 404"""
        mock_popen = mocker.patch("subprocess.Popen")

        response = await client.post("/api/spiders/nonexistent/run")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Spider 'nonexistent' not found"

        # 确保没有启动进程
        mock_popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_running_spider_returns_409(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], test_session: AsyncSession, mocker
    ):
        """Spider 正在运行时 POST /api/spiders/{name}/run 返回 409"""
        from huginn.core.models import SpiderRun

        mock_popen = mocker.patch("subprocess.Popen")

        # 创建一个正在运行的记录
        running_run = SpiderRun(
            spider_name="hackernews",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        test_session.add(running_run)
        await test_session.flush()

        response = await client.post("/api/spiders/hackernews/run")
        assert response.status_code == status.HTTP_409_CONFLICT

        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Spider 'hackernews' is already running"

        # 确保没有启动新进程
        mock_popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_creates_spider_run_record_with_status_running(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], test_session: AsyncSession, mocker
    ):
        """spider_runs 表中创建了 status=running 的记录"""
        from huginn.core.models import SpiderRun
        from sqlalchemy import select

        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # 触发运行
        response = await client.post("/api/spiders/hackernews/run")
        assert response.status_code == status.HTTP_202_ACCEPTED

        run_id = response.json()["run_id"]

        # 查询数据库中的运行记录
        query = select(SpiderRun).where(SpiderRun.id == run_id)
        result = await test_session.execute(query)
        run = result.scalar_one_or_none()

        assert run is not None
        assert run.spider_name == "hackernews"
        assert run.status == "running"
        assert run.started_at is not None
        assert run.finished_at is None

    @pytest.mark.asyncio
    async def test_trigger_returns_immediately_without_waiting(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], test_session: AsyncSession, mocker
    ):
        """接口立即返回，不等待采集完成"""
        # Mock 一个"慢"进程，确保接口不会等待
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # 记录开始时间
        import time
        start = time.time()

        response = await client.post("/api/spiders/hackernews/run")

        elapsed = time.time() - start

        # 接口应该立即返回（不超过 1 秒）
        assert elapsed < 1.0
        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.asyncio
    async def test_trigger_starts_scrapy_process(
        self, client: AsyncClient, sample_spiders: list[SpiderRegistry], test_session: AsyncSession, mocker
    ):
        """验证调用 subprocess.Popen 启动 scrapy crawl {name}"""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        response = await client.post("/api/spiders/hackernews/run")
        assert response.status_code == status.HTTP_202_ACCEPTED

        # 验证 Popen 被正确调用
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        # 检查命令包含 scrapy crawl hackernews
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args")
        assert "scrapy" in str(cmd)
        assert "crawl" in str(cmd)
        assert "hackernews" in str(cmd)
