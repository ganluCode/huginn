"""FastAPI 主应用测试

测试 FastAPI 应用配置、CORS 中间件、异常处理和基础路由。
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text

from huginn.api.main import app
from huginn.core.exceptions import HuginnError, StorageError


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """创建测试客户端

    使用 FastAPI 提供的 TestClient 进行 API 测试。
    """
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoint:
    """测试 /api/health 健康检查端点"""

    def test_health_endpoint_exists(self, client: TestClient):
        """GET /api/health 路由存在并返回响应"""
        response = client.get("/api/health")
        # 期待返回 200 状态码（即使只是占位响应）
        assert response.status_code == status.HTTP_200_OK

    def test_health_response_structure(self, client: TestClient):
        """健康检查响应包含基本结构"""
        response = client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK
        # 响应应该包含数据（即使是最简单的占位响应）
        assert response.json() is not None

    def test_health_response_format(self, client: TestClient):
        """健康检查返回正确格式：status、postgres、redis 字段"""
        response = client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "status" in data
        assert "postgres" in data
        assert "redis" in data
        assert data["status"] == "ok"
        assert isinstance(data["postgres"], bool)
        assert isinstance(data["redis"], bool)

    @patch("huginn.api.deps.AsyncSessionLocal")
    @patch("huginn.api.deps.Redis")
    def test_health_when_postgres_unavailable(
        self, mock_redis: MagicMock, mock_session_local: MagicMock, client: TestClient
    ):
        """PG 不可用时响应 postgres=false 且 status 仍为 ok"""
        # Mock PG session 抛出异常
        mock_session = AsyncMock()
        mock_session.__aenter__.side_effect = Exception("PG connection failed")
        mock_session_local.return_value = mock_session

        # Mock Redis 正常
        mock_redis_inst = MagicMock()
        mock_redis_inst.ping.return_value = True
        mock_redis.from_url.return_value = mock_redis_inst

        # 清除 Redis 客户端缓存（模拟重新连接）
        import huginn.api.deps as deps_module
        deps_module._redis_client = None

        # 使用新的 TestClient 实例，确保 patch 生效
        with TestClient(app) as test_client:
            response = test_client.get("/api/health")
            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert data["status"] == "ok"
            assert data["postgres"] is False
            # Redis 应该正常
            assert isinstance(data["redis"], bool)

    @patch("huginn.api.deps.AsyncSessionLocal")
    @patch("huginn.api.deps.Redis")
    def test_health_when_redis_unavailable(
        self, mock_redis: MagicMock, mock_session_local: MagicMock, client: TestClient
    ):
        """Redis 不可用时响应 redis=false 且 status 仍为 ok"""
        # Mock Redis 抛出异常
        mock_redis.from_url.side_effect = Exception("Redis connection failed")

        # Mock PG 正常
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        # 模拟成功的 SELECT 1 查询
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result
        mock_session_local.return_value = mock_session

        # 清除 Redis 客户端缓存（模拟重新连接）
        import huginn.api.deps as deps_module
        deps_module._redis_client = None

        # 使用新的 TestClient 实例，确保 patch 生效
        with TestClient(app) as test_client:
            response = test_client.get("/api/health")
            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert data["status"] == "ok"
            assert data["redis"] is False
            # PG 应该正常
            assert isinstance(data["postgres"], bool)


class TestCORSMiddleware:
    """测试 CORS 中间件配置"""

    def test_cors_allows_localhost_5173(self, client: TestClient):
        """OPTIONS 请求 localhost:5173 返回 CORS 头 Access-Control-Allow-Origin"""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_cors_allows_localhost_3000(self, client: TestClient):
        """OPTIONS 请求 localhost:3000 返回 CORS 头 Access-Control-Allow-Origin"""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_cors_allows_credentials(self, client: TestClient):
        """CORS 配置允许携带凭证"""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"


class TestHuginnErrorHandler:
    """测试 HuginnError 异常处理器"""

    def test_huginn_error_returns_json_detail(self, client: TestClient):
        """触发 HuginnError 时响应为 JSON {'detail': '...'} 格式"""
        # 创建一个测试路由来触发异常
        @app.get("/api/test-error")
        async def test_error():
            raise HuginnError("Something went wrong")

        with TestClient(app) as test_client:
            response = test_client.get("/api/test-error")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json() == {"detail": "Something went wrong"}

    def test_storage_error_inherits_huginn_error_handling(self, client: TestClient):
        """StorageError（继承自 HuginnError）也被异常处理器正确处理"""
        @app.get("/api/test-storage-error")
        async def test_storage_error():
            raise StorageError("Database connection failed")

        with TestClient(app) as test_client:
            response = test_client.get("/api/test-storage-error")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json() == {"detail": "Database connection failed"}

    def test_huginn_error_with_empty_message(self, client: TestClient):
        """HuginnError 没有消息时仍返回有效的 JSON 响应"""
        @app.get("/api/test-empty-error")
        async def test_empty_error():
            raise HuginnError()

        with TestClient(app) as test_client:
            response = test_client.get("/api/test-empty-error")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            # 空消息时应该有 detail 字段，可能为空字符串
            assert "detail" in response.json()


class TestAPIPrefix:
    """测试 API 路由前缀"""

    def test_all_routes_mounted_to_api_prefix(self, client: TestClient):
        """所有路由都挂载到 /api 前缀下"""
        # /api/health 应该存在
        response = client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK

        # /health（无前缀）应该不存在
        response = client.get("/health")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestApplicationConfig:
    """测试应用配置"""

    def test_app_has_title(self):
        """应用配置了 title"""
        assert app.title == "Huginn API"

    def test_app_can_be_imported(self):
        """huginn.api.main:app 可被 import 不报错"""
        from huginn.api.main import app as imported_app  # noqa: F401, PLW0127

        assert imported_app is not None
        assert imported_app.title == "Huginn API"
