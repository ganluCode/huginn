"""Spider 管理 API 测试

测试 Spider 列表、详情、触发运行等接口。
"""

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select

from huginn.api.main import app
from huginn.core.models import SpiderRegistry


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """创建测试客户端"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_spiders(db_session) -> list[SpiderRegistry]:
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

    db_session.add_all(spiders)
    db_session.commit()

    return spiders


class TestSpiderListEndpoint:
    """测试 GET /api/spiders 端点"""

    def test_spider_list_returns_200_with_items_and_total(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders 返回 200，body 含 items 数组和 total 整数"""
        response = client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_spider_list_filter_by_category(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?category=tech 只返回 category=tech 的 Spider"""
        response = client.get("/api/spiders?category=tech")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        # 验证所有返回的 Spider category 都是 tech
        for spider in data["items"]:
            assert spider["category"] == "tech"

    def test_spider_list_filter_by_enabled_true(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?enabled=true 只返回 enabled=true 的 Spider"""
        response = client.get("/api/spiders?enabled=true")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        # 验证所有返回的 Spider enabled 都是 True
        for spider in data["items"]:
            assert spider["enabled"] is True

    def test_spider_list_filter_by_enabled_false(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """GET /api/spiders?enabled=false 只返回 enabled=false 的 Spider"""
        response = client.get("/api/spiders?enabled=false")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        # 验证返回的 Spider enabled 是 False
        assert data["items"][0]["enabled"] is False

    def test_spider_list_no_filters_returns_all(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """不传参数时返回所有 Spider"""
        response = client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_spider_list_ordered_by_created_at_desc(
        self, client: TestClient, db_session
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

        db_session.add_all([spider1, spider2, spider3])
        db_session.commit()

        response = client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        items = data["items"]
        # 验证顺序：spider2 (300000) > spider3 (200000) > spider1 (100000)
        assert items[0]["name"] == "spider2"
        assert items[1]["name"] == "spider3"
        assert items[2]["name"] == "spider1"

    def test_spider_list_response_structure(
        self, client: TestClient, sample_spiders: list[SpiderRegistry]
    ):
        """验证响应包含 SpiderItem 的所有必需字段"""
        response = client.get("/api/spiders")
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

    def test_spider_list_empty_database(
        self, client: TestClient, db_session
    ):
        """数据库为空时返回空列表"""
        response = client.get("/api/spiders")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0
