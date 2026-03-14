"""Spider API 端点测试

测试 Spider 列表、详情、触发运行、运行历史等接口。
使用 FastAPI 的 dependency override 机制来 mock 数据库依赖。
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.api.deps import get_db_session
from huginn.api.main import app
from huginn.core.models import SpiderRegistry, SpiderRun


class MockDbSession(AsyncMock):
    """Mock AsyncSession，正确处理 async context manager"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置为 spec=AsyncSession 但不严格要求所有方法
        self._spec_class = AsyncSession

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def create_mock_session(**overrides) -> AsyncMock:
    """创建配置好的 mock session"""
    mock = MockDbSession(spec=AsyncSession)

    # 默认的 execute 返回值
    default_result = MagicMock()
    default_result.scalars.return_value.all.return_value = []
    default_result.scalar_one_or_none.return_value = None
    mock.execute.return_value = default_result

    # 应用覆盖
    for key, value in overrides.items():
        setattr(mock, key, value)

    return mock


class TestHealthEndpoint:
    """测试 /api/health 健康检查端点"""

    def test_health_returns_status_ok(self):
        """GET /api/health 测试通过（status=ok）"""
        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert data["status"] == "ok"


class TestSpiderListEndpoint:
    """测试 GET /api/spiders 端点"""

    def test_spider_list_returns_items_and_total(self):
        """GET /api/spiders 测试通过（返回 items 和 total）"""
        now = datetime.now(timezone.utc)
        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_spider]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert "total" in data
                assert len(data["items"]) == 1
                assert data["total"] == 1
                assert data["items"][0]["name"] == "hackernews"
        finally:
            app.dependency_overrides = {}

    def test_spider_list_filter_by_category(self):
        """GET /api/spiders?category=tech 筛选测试通过"""
        now = datetime.now(timezone.utc)

        tech_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [tech_spider]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders?category=tech")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data["items"]) == 1
                assert data["items"][0]["category"] == "tech"
                assert data["items"][0]["name"] == "hackernews"
        finally:
            app.dependency_overrides = {}

    def test_spider_list_filter_by_enabled(self):
        """GET /api/spiders?enabled=true 筛选测试通过"""
        now = datetime.now(timezone.utc)

        enabled_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [enabled_spider]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders?enabled=true")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data["items"]) == 1
                assert data["items"][0]["enabled"] is True
        finally:
            app.dependency_overrides = {}

    def test_spider_list_empty_when_db_unavailable(self):
        """数据库不可用时返回空列表"""
        async def mock_get_db_none():
            yield None

        app.dependency_overrides[get_db_session] = mock_get_db_none

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["items"] == []
                assert data["total"] == 0
        finally:
            app.dependency_overrides = {}


class TestSpiderDetailEndpoint:
    """测试 GET /api/spiders/{name} 端点"""

    def test_spider_detail_returns_config_field(self):
        """GET /api/spiders/{name} 存在的情况测试"""
        now = datetime.now(timezone.utc)
        config = {"allowed_domains": ["news.ycombinator.com"], "start_urls": ["https://news.ycombinator.com"]}

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            config=config,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_session = create_mock_session()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_spider

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["name"] == "hackernews"
                assert "config" in data
                assert data["config"] == config
        finally:
            app.dependency_overrides = {}

    def test_spider_detail_returns_404_when_not_found(self):
        """GET /api/spiders/{name} 不存在的情况测试（404）"""
        mock_session = create_mock_session()
        # scalar_one_or_none 返回 None 表示 Spider 不存在

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/nonexistent")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert "detail" in data
                assert "nonexistent" in data["detail"]
        finally:
            app.dependency_overrides = {}

    def test_spider_detail_returns_404_when_db_unavailable(self):
        """数据库不可用时返回 404"""
        async def mock_get_db_none():
            yield None

        app.dependency_overrides[get_db_session] = mock_get_db_none

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert "detail" in data
        finally:
            app.dependency_overrides = {}


class TestSpiderTriggerEndpoint:
    """测试 POST /api/spiders/{name}/run 端点"""

    def test_trigger_run_returns_202_when_spider_exists_and_not_running(self):
        """POST /api/spiders/{name}/run 的 202 情况测试"""
        from unittest.mock import patch

        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_session = create_mock_session()

        # 第一次调用：查询 Spider - 返回 spider
        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        # 第二次调用：查询运行记录 - 返回 None（未在运行）
        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [spider_result, run_result]

        # Mock flush 来设置 run.id
        async def mock_flush():
            # 找到被 add 的 SpiderRun 并设置 id
            for mock_call in mock_session.add.call_args_list:
                if mock_call:
                    obj = mock_call[0][0] if mock_call[0] else None
                    if obj and isinstance(obj, SpiderRun):
                        obj.id = 123  # 设置 mock run_id

        mock_session.flush = AsyncMock(side_effect=mock_flush)
        mock_session.add = MagicMock()

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with patch("huginn.api.routers.spiders.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_popen.return_value = mock_process

                with TestClient(app) as client:
                    response = client.post("/api/spiders/hackernews/run")

                    assert response.status_code == status.HTTP_202_ACCEPTED
                    data = response.json()
                    assert "message" in data
                    assert "run_id" in data
                    assert "started successfully" in data["message"].lower()
        finally:
            app.dependency_overrides = {}

    def test_trigger_run_returns_404_when_spider_not_found(self):
        """POST /api/spiders/{name}/run 的 404 情况测试"""
        mock_session = create_mock_session()
        # Spider 不存在
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.post("/api/spiders/nonexistent/run")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert "detail" in data
                assert "nonexistent" in data["detail"].lower()
        finally:
            app.dependency_overrides = {}

    def test_trigger_run_returns_409_when_spider_already_running(self):
        """POST /api/spiders/{name}/run 的 409 情况测试（已在运行）"""
        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="running",
            item_count=100,
            created_at=now,
        )

        mock_run = SpiderRun(
            id=1,
            spider_name="hackernews",
            started_at=now,
            status="running",
            item_count=0,
        )

        mock_session = create_mock_session()

        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = mock_run

        mock_session.execute.side_effect = [spider_result, run_result]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.post("/api/spiders/hackernews/run")

                assert response.status_code == status.HTTP_409_CONFLICT
                data = response.json()
                assert "detail" in data
                assert "already running" in data["detail"].lower()
        finally:
            app.dependency_overrides = {}


class TestSpiderRunsEndpoint:
    """测试 GET /api/spiders/{name}/runs 端点"""

    def test_runs_returns_items_and_total(self):
        """GET /api/spiders/{name}/runs 测试通过（返回 items 和 total）"""
        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=100,
            created_at=now,
        )

        mock_run1 = SpiderRun(
            id=1,
            spider_name="hackernews",
            started_at=now,
            finished_at=now,
            status="success",
            item_count=100,
            duration_ms=1000,
        )

        mock_run2 = SpiderRun(
            id=2,
            spider_name="hackernews",
            started_at=now,
            finished_at=None,
            status="running",
            item_count=0,
        )

        mock_session = create_mock_session()

        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = [mock_run1, mock_run2]

        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = [mock_run1]

        mock_session.execute.side_effect = [spider_result, count_result, runs_result]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews/runs")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert "total" in data
                assert data["total"] == 2
                assert len(data["items"]) == 1
        finally:
            app.dependency_overrides = {}

    def test_runs_supports_pagination_limit(self):
        """GET /api/spiders/{name}/runs 分页测试（limit 参数）"""
        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now,
        )

        mock_session = create_mock_session()

        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []

        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [spider_result, count_result, runs_result]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews/runs?limit=5")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert "total" in data
        finally:
            app.dependency_overrides = {}

    def test_runs_truncates_limit_to_max_100(self):
        """GET /api/spiders/{name}/runs limit 参数截断为 100"""
        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now,
        )

        mock_session = create_mock_session()

        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []

        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [spider_result, count_result, runs_result]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews/runs?limit=200")

                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides = {}

    def test_runs_supports_offset(self):
        """GET /api/spiders/{name}/runs 分页测试（offset 参数）"""
        now = datetime.now(timezone.utc)

        mock_spider = SpiderRegistry(
            name="hackernews",
            engine="scrapy",
            category="tech",
            enabled=True,
            created_at=now,
        )

        mock_session = create_mock_session()

        spider_result = MagicMock()
        spider_result.scalar_one_or_none.return_value = mock_spider

        count_result = MagicMock()
        count_result.scalars.return_value.all.return_value = []

        runs_result = MagicMock()
        runs_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [spider_result, count_result, runs_result]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/hackernews/runs?offset=10")

                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides = {}

    def test_runs_returns_404_when_spider_not_found(self):
        """GET /api/spiders/{name}/runs 404 测试（Spider 不存在）"""
        mock_session = create_mock_session()
        # Spider 不存在

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db

        try:
            with TestClient(app) as client:
                response = client.get("/api/spiders/nonexistent/runs")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert "detail" in data
                assert "nonexistent" in data["detail"].lower()
        finally:
            app.dependency_overrides = {}
