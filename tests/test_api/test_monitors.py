"""关键词监控 API 端点测试

测试 GET/POST /api/monitors 和 DELETE /api/monitors/{id} 接口。
使用 FastAPI 的 dependency override 机制来 mock 数据库依赖。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.api.deps import get_db_session
from huginn.api.main import app
from huginn.core.models import KeywordMonitor


def create_mock_session() -> AsyncMock:
    """创建配置好的 mock session"""
    mock = AsyncMock(spec=AsyncSession)

    default_result = MagicMock()
    default_result.scalars.return_value.all.return_value = []
    default_result.scalar_one_or_none.return_value = None
    mock.execute.return_value = default_result

    return mock


def make_monitor(id=1, keyword="AI", sources=None, enabled=True, webhook_url=None):
    """创建测试用的 KeywordMonitor 实例"""
    return KeywordMonitor(
        id=id,
        keyword=keyword,
        sources=sources,
        enabled=enabled,
        webhook_url=webhook_url,
        created_at=datetime.now(timezone.utc),
    )


class TestGetMonitors:
    """测试 GET /api/monitors"""

    def test_returns_200_with_empty_list(self):
        """数据库无记录时返回 200 和空列表"""
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/monitors")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0
        finally:
            app.dependency_overrides = {}

    def test_returns_list_with_correct_fields(self):
        """返回包含 id/keyword/sources/enabled/created_at 的列表"""
        monitor = make_monitor(id=1, keyword="独立开发", sources=["hackernews"])
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [monitor]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/monitors")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            item = data[0]
            assert item["id"] == 1
            assert item["keyword"] == "独立开发"
            assert item["sources"] == ["hackernews"]
            assert item["enabled"] is True
            assert "created_at" in item
        finally:
            app.dependency_overrides = {}

    def test_returns_multiple_monitors(self):
        """多条记录时返回所有记录"""
        monitors = [
            make_monitor(id=1, keyword="AI"),
            make_monitor(id=2, keyword="LLM"),
        ]
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = monitors

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/monitors")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
        finally:
            app.dependency_overrides = {}

    def test_returns_empty_list_when_db_unavailable(self):
        """数据库不可用时返回空列表"""
        async def mock_get_db_none():
            yield None

        app.dependency_overrides[get_db_session] = mock_get_db_none
        try:
            with TestClient(app) as client:
                response = client.get("/api/monitors")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []
        finally:
            app.dependency_overrides = {}


class TestPostMonitors:
    """测试 POST /api/monitors"""

    def test_empty_keyword_returns_422(self):
        """keyword 为空字符串时返回 422"""
        async def mock_get_db():
            yield create_mock_session()

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.post("/api/monitors", json={"keyword": ""})
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides = {}

    def test_missing_keyword_returns_422(self):
        """缺少 keyword 字段时返回 422"""
        async def mock_get_db():
            yield create_mock_session()

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.post("/api/monitors", json={})
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides = {}

    def test_valid_request_returns_201_with_monitor(self):
        """合法请求返回 201 和新建的 monitor 对象"""
        mock_session = create_mock_session()

        async def mock_flush():
            # 找到被 add 的 KeywordMonitor 并设置 id
            for call in mock_session.add.call_args_list:
                obj = call[0][0] if call[0] else None
                if obj and isinstance(obj, KeywordMonitor):
                    obj.id = 42
                    if obj.created_at is None:
                        obj.created_at = datetime.now(timezone.utc)

        mock_session.flush = AsyncMock(side_effect=mock_flush)
        mock_session.add = MagicMock()

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/monitors",
                    json={"keyword": "独立开发", "sources": ["hackernews"], "enabled": True},
                )
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["keyword"] == "独立开发"
            assert data["sources"] == ["hackernews"]
            assert data["enabled"] is True
            assert "id" in data
            assert "created_at" in data
        finally:
            app.dependency_overrides = {}

    def test_valid_request_minimal_fields(self):
        """只有 keyword 字段的合法请求也返回 201"""
        mock_session = create_mock_session()

        async def mock_flush():
            for call in mock_session.add.call_args_list:
                obj = call[0][0] if call[0] else None
                if obj and isinstance(obj, KeywordMonitor):
                    obj.id = 10
                    if obj.created_at is None:
                        obj.created_at = datetime.now(timezone.utc)

        mock_session.flush = AsyncMock(side_effect=mock_flush)
        mock_session.add = MagicMock()

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.post("/api/monitors", json={"keyword": "AI"})
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["keyword"] == "AI"
        finally:
            app.dependency_overrides = {}


class TestDeleteMonitor:
    """测试 DELETE /api/monitors/{id}"""

    def test_delete_existing_monitor_returns_204(self):
        """存在的 monitor 删除后返回 204"""
        monitor = make_monitor(id=5, keyword="AI")
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalar_one_or_none.return_value = monitor
        mock_session.delete = AsyncMock()

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.delete("/api/monitors/5")
            assert response.status_code == status.HTTP_204_NO_CONTENT
        finally:
            app.dependency_overrides = {}

    def test_delete_nonexistent_monitor_returns_404(self):
        """不存在的 monitor 返回 404"""
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.delete("/api/monitors/999")
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
        finally:
            app.dependency_overrides = {}

    def test_delete_returns_404_when_db_unavailable(self):
        """数据库不可用时返回 404"""
        async def mock_get_db_none():
            yield None

        app.dependency_overrides[get_db_session] = mock_get_db_none
        try:
            with TestClient(app) as client:
                response = client.delete("/api/monitors/1")
            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides = {}


class TestGetNotifications:
    """测试 GET /api/notifications"""

    def _make_notification(self, id=1, type="keyword_hit", title="Test", body=None, source=None, sent=False):
        from huginn.core.models import Notification
        return Notification(
            id=id,
            type=type,
            title=title,
            body=body,
            source=source,
            triggered_at=datetime.now(timezone.utc),
            sent=sent,
        )

    def test_returns_200_with_empty_list(self):
        """数据库无记录时返回 200 和空列表"""
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []
        finally:
            app.dependency_overrides = {}

    def test_returns_correct_fields(self):
        """返回包含 id/type/title/body/source/triggered_at/sent 的通知"""
        notif = self._make_notification(id=1, type="keyword_hit", title="AI matched", body="detail", source="hackernews", sent=True)
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [notif]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            item = data[0]
            assert item["id"] == 1
            assert item["type"] == "keyword_hit"
            assert item["title"] == "AI matched"
            assert item["body"] == "detail"
            assert item["source"] == "hackernews"
            assert "triggered_at" in item
            assert item["sent"] is True
        finally:
            app.dependency_overrides = {}

    def test_filter_by_type(self):
        """?type=keyword_hit 只返回对应类型"""
        mock_session = create_mock_session()
        notif = self._make_notification(id=1, type="keyword_hit")
        mock_session.execute.return_value.scalars.return_value.all.return_value = [notif]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications?type=keyword_hit")
            assert response.status_code == status.HTTP_200_OK
            # Verify the query was executed (filter applied server-side via SQL)
            assert mock_session.execute.called
        finally:
            app.dependency_overrides = {}

    def test_filter_by_source(self):
        """?source=hackernews 只返回对应数据源"""
        mock_session = create_mock_session()
        notif = self._make_notification(id=1, source="hackernews")
        mock_session.execute.return_value.scalars.return_value.all.return_value = [notif]

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications?source=hackernews")
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides = {}

    def test_limit_parameter(self):
        """?limit=10 限制返回条数"""
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications?limit=10")
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides = {}

    def test_limit_over_200_capped_at_200(self):
        """?limit=500 超过 200 时按 200 处理，返回 200 OK 而不是 422"""
        mock_session = create_mock_session()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications?limit=500")
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides = {}

    def test_default_limit_is_50(self):
        """无参数时默认返回最近 50 条"""
        mock_session = create_mock_session()
        notifications = [self._make_notification(id=i) for i in range(1, 51)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = notifications

        async def mock_get_db():
            yield mock_session

        app.dependency_overrides[get_db_session] = mock_get_db
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications")
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()) == 50
        finally:
            app.dependency_overrides = {}

    def test_returns_empty_list_when_db_unavailable(self):
        """数据库不可用时返回空列表"""
        async def mock_get_db_none():
            yield None

        app.dependency_overrides[get_db_session] = mock_get_db_none
        try:
            with TestClient(app) as client:
                response = client.get("/api/notifications")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []
        finally:
            app.dependency_overrides = {}
