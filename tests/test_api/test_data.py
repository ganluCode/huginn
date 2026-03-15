"""数据查询 API 端点测试

测试 /api/data 相关接口，包括查询、统计、导出等。
使用 unittest.mock 来模拟 PostgresBackend 的行为。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from huginn.api.main import app


class TestDataQueryEndpoint:
    """测试 GET /api/data 端点"""

    def test_data_query_default_params_returns_correct_structure(self):
        """GET /api/data 默认参数返回 200 且结构正确"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert "total" in data
                assert "limit" in data
                assert "offset" in data
                assert data["items"] == []
                assert data["total"] == 0

    def test_data_query_with_source_filter(self):
        """GET /api/data?source=xx 筛选有效"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data?source=hackernews")

                assert response.status_code == status.HTTP_200_OK
                # Verify query was called with source parameter
                mock_backend.query.assert_called_once()
                call_kwargs = mock_backend.query.call_args.kwargs
                assert call_kwargs.get("source") == "hackernews"

    def test_data_query_limit_truncated_to_200(self):
        """GET /api/data?limit=300 返回条数不超过 200"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data?limit=300")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                # Verify limit was truncated to 200
                assert data["limit"] == 200
                # Verify query was called with limit=200
                call_kwargs = mock_backend.query.call_args.kwargs
                assert call_kwargs.get("limit") == 200

    def test_data_query_invalid_time_from_returns_422(self):
        """GET /api/data?time_from=invalid 返回 422"""

        with TestClient(app) as client:
            response = client.get("/api/data?time_from=invalid")

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_data_query_nonexistent_source_returns_empty(self):
        """GET /api/data?source=nonexistent 返回 200 且 items=[], total=0"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data?source=nonexistent")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["items"] == []
                assert data["total"] == 0

    def test_data_query_with_keyword_filter(self):
        """GET /api/data?keyword=AI 仅返回包含 AI 的数据"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data?keyword=AI")

                assert response.status_code == status.HTTP_200_OK
                # Verify query was called with keyword parameter
                mock_backend.query.assert_called_once()
                call_kwargs = mock_backend.query.call_args.kwargs
                assert call_kwargs.get("keyword") == "AI"

    def test_data_query_limit_field_reflects_actual_value(self):
        """响应中 limit 字段反映实际使用的 limit 值（截断后）"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend.count = AsyncMock(return_value=0)
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                # Test with limit=50 (should be 50)
                response = client.get("/api/data?limit=50")
                data = response.json()
                assert data["limit"] == 50

                # Test with limit=300 (should be truncated to 200)
                mock_backend.query.reset_mock()
                response = client.get("/api/data?limit=300")
                data = response.json()
                assert data["limit"] == 200


class TestDataStatsEndpoint:
    """测试 GET /api/data/stats 端点"""

    def test_stats_returns_correct_structure(self):
        """GET /api/data/stats 返回结构正确（含 total, by_source, by_category, by_date）"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.get_stats = AsyncMock(
                return_value={
                    "total": 100,
                    "by_source": [{"source": "hackernews", "count": 50}],
                    "by_category": [{"category": "tech", "count": 100}],
                    "by_date": [{"date": "2026-03-15", "count": 100}],
                }
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/stats")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "total" in data
                assert "by_source" in data
                assert "by_category" in data
                assert "by_date" in data
                assert data["total"] == 100

    def test_stats_with_days_zero(self):
        """GET /api/data/stats?days=0 不报错"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.get_stats = AsyncMock(
                return_value={
                    "total": 50,
                    "by_source": [],
                    "by_category": [],
                    "by_date": [],
                }
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/stats?days=0")

                assert response.status_code == status.HTTP_200_OK
                # Verify get_stats was called with days=0
                mock_backend.get_stats.assert_called_once_with(days=0)

    def test_stats_with_custom_days(self):
        """GET /api/data/stats?days=1 仅统计最近1天数据"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.get_stats = AsyncMock(
                return_value={
                    "total": 10,
                    "by_source": [],
                    "by_category": [],
                    "by_date": [],
                }
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/stats?days=1")

                assert response.status_code == status.HTTP_200_OK
                # Verify get_stats was called with days=1
                mock_backend.get_stats.assert_called_once_with(days=1)


class TestDataSourcesEndpoint:
    """测试 GET /api/data/sources 端点"""

    def test_sources_returns_correct_structure(self):
        """GET /api/data/sources 返回 {items: [...]} 结构"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.get_sources_summary = AsyncMock(
                return_value=[
                    {
                        "source": "hackernews",
                        "category": "tech",
                        "total_count": 100,
                        "latest_at": "2026-03-15T00:00:00Z",
                    }
                ]
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/sources")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "items" in data
                assert isinstance(data["items"], list)
                assert len(data["items"]) == 1

    def test_sources_empty_when_no_data(self):
        """系统无数据时返回 {\"items\": []}"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.get_sources_summary = AsyncMock(return_value=[])
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/sources")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["items"] == []


class TestDataExportEndpoint:
    """测试 GET /api/data/export 端点"""

    def test_export_csv_returns_correct_content_type(self):
        """GET /api/data/export?format=csv 返回 text/csv 响应且含表头"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=csv")

                assert response.status_code == status.HTTP_200_OK
                assert "text/csv" in response.headers["content-type"]
                assert "attachment" in response.headers.get("content-disposition", "").lower()
                # Check CSV header
                content = response.content.decode()
                assert content.startswith("id,source,category,collected_at,title,url,data")

    def test_export_json_returns_json_array(self):
        """GET /api/data/export?format=json 返回 JSON 数组"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "source": "hackernews",
                        "category": "tech",
                        "collected_at": "2026-03-15T00:00:00Z",
                        "data": {"title": "Test", "url": "http://example.com"},
                    }
                ]
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=json")

                assert response.status_code == status.HTTP_200_OK
                assert "application/json" in response.headers["content-type"]
                assert "attachment" in response.headers.get("content-disposition", "").lower()
                # Verify JSON array
                import json

                data = json.loads(response.content)
                assert isinstance(data, list)

    def test_export_invalid_format_returns_422(self):
        """GET /api/data/export?format=xml 返回 422"""

        with TestClient(app) as client:
            response = client.get("/api/data/export?format=xml")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_export_csv_with_data_includes_rows(self):
        """CSV export with data includes rows"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "source": "hackernews",
                        "category": "tech",
                        "collected_at": "2026-03-15T00:00:00Z",
                        "data": {"title": "Test Title", "url": "http://example.com"},
                    }
                ]
            )
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=csv")

                content = response.content.decode()
                # Should have header + 1 data row
                lines = content.strip().split("\n")
                assert len(lines) >= 1  # At least header
                # Strip any trailing whitespace from the header line
                assert lines[0].strip() == "id,source,category,collected_at,title,url,data"

    def test_export_limit_max_10000(self):
        """数据量超过10000条时只输出前10000条"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=json")

                # Verify query was called with limit=10000
                mock_backend.query.assert_called_once()
                call_kwargs = mock_backend.query.call_args.kwargs
                assert call_kwargs.get("limit") == 10000

    def test_export_csv_empty_data_returns_header_only(self):
        """无匹配数据时 CSV 只返回表头行"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=csv")

                content = response.content.decode()
                lines = content.strip().split("\n")
                # Should only have header
                assert len(lines) == 1
                # Strip any trailing whitespace from the header line
                assert lines[0].strip() == "id,source,category,collected_at,title,url,data"

    def test_export_json_empty_data_returns_empty_array(self):
        """无匹配数据时 JSON 返回 []"""

        with patch("huginn.api.routers.data.PostgresBackend") as mock_backend_class:
            mock_backend = AsyncMock()
            mock_backend.query = AsyncMock(return_value=[])
            mock_backend_class.return_value = mock_backend

            with TestClient(app) as client:
                response = client.get("/api/data/export?format=json")

                import json

                data = json.loads(response.content)
                assert data == []
