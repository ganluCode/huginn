"""测试 API 响应模型（Pydantic schemas）

测试 Spider 相关的响应模型，确保字段定义正确、
datetime 序列化配置正确、模型可正常实例化。
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from huginn.api.schemas import (
    RunItem,
    RunListResponse,
    SpiderDetail,
    SpiderItem,
    SpiderListResponse,
    TriggerResponse,
)


class TestSpiderItem:
    """测试 SpiderItem 模型"""

    def test_spider_item_has_all_required_fields(self):
        """SpiderItem 包含 name、engine、category、schedule、enabled、last_run_at、last_status、item_count、created_at"""
        now = datetime.now(timezone.utc)
        item = SpiderItem(
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

        assert item.name == "hackernews"
        assert item.engine == "scrapy"
        assert item.category == "tech"
        assert item.schedule == "0 */6 * * *"
        assert item.enabled is True
        assert item.last_run_at == now
        assert item.last_status == "success"
        assert item.item_count == 100
        assert item.created_at == now

    def test_spider_item_optional_fields_can_be_none(self):
        """SpiderItem 的可选字段（schedule、category、last_run_at、last_status）可以为 None"""
        now = datetime.now(timezone.utc)
        item = SpiderItem(
            name="test_spider",
            engine="scrapy",
            category=None,
            schedule=None,
            enabled=False,
            last_run_at=None,
            last_status=None,
            item_count=0,
            created_at=now,
        )

        assert item.category is None
        assert item.schedule is None
        assert item.last_run_at is None
        assert item.last_status is None

    def test_spider_item_serializes_datetime_to_utc_iso(self):
        """datetime 字段序列化为 ISO 8601 UTC 格式"""
        now = datetime.now(timezone.utc)
        item = SpiderItem(
            name="test",
            engine="scrapy",
            category="tech",
            schedule="*/30 * * * *",
            enabled=True,
            last_run_at=now,
            last_status="running",
            item_count=50,
            created_at=now,
        )

        data = item.model_dump(mode="json")
        # 验证 datetime 被序列化为带 Z 后缀的 ISO 格式
        assert "last_run_at" in data
        assert "created_at" in data
        # ISO 8601 格式检查
        assert data["last_run_at"].endswith("Z") or "+" in data["last_run_at"]
        assert data["created_at"].endswith("Z") or "+" in data["created_at"]


class TestSpiderDetail:
    """测试 SpiderDetail 模型"""

    def test_spider_detail_inherits_all_spider_item_fields(self):
        """SpiderDetail 继承 SpiderItem 的所有字段"""
        now = datetime.now(timezone.utc)
        config = {"allowed_domains": ["example.com"], "start_urls": ["https://example.com"]}
        detail = SpiderDetail(
            name="github_trending",
            engine="scrapy",
            category="tech",
            schedule="0 */6 * * *",
            enabled=True,
            last_run_at=now,
            last_status="success",
            item_count=200,
            created_at=now,
            config=config,
        )

        assert detail.name == "github_trending"
        assert detail.engine == "scrapy"
        assert detail.category == "tech"
        assert detail.enabled is True
        assert detail.item_count == 200
        assert detail.last_run_at == now

    def test_spider_detail_has_config_field(self):
        """SpiderDetail 增加 config 字段"""
        now = datetime.now(timezone.utc)
        config = {"setting": "value"}
        detail = SpiderDetail(
            name="test",
            engine="scrapy",
            category="finance",
            schedule=None,
            enabled=False,
            last_run_at=None,
            last_status=None,
            item_count=0,
            created_at=now,
            config=config,
        )

        assert detail.config == config

    def test_spider_detail_config_can_be_none(self):
        """SpiderDetail 的 config 字段可以为 None"""
        now = datetime.now(timezone.utc)
        detail = SpiderDetail(
            name="test",
            engine="rpa",
            category="social",
            schedule=None,
            enabled=False,
            last_run_at=None,
            last_status=None,
            item_count=0,
            created_at=now,
            config=None,
        )

        assert detail.config is None


class TestSpiderListResponse:
    """测试 SpiderListResponse 模型"""

    def test_spider_list_response_has_items_and_total(self):
        """SpiderListResponse 包含 items 数组和 total 整数"""
        now = datetime.now(timezone.utc)
        items = [
            SpiderItem(
                name="spider1",
                engine="scrapy",
                category="tech",
                schedule="0 */6 * * *",
                enabled=True,
                last_run_at=now,
                last_status="success",
                item_count=100,
                created_at=now,
            ),
            SpiderItem(
                name="spider2",
                engine="rpa",
                category="social",
                schedule=None,
                enabled=False,
                last_run_at=None,
                last_status=None,
                item_count=0,
                created_at=now,
            ),
        ]

        response = SpiderListResponse(items=items, total=2)

        assert len(response.items) == 2
        assert response.total == 2
        assert response.items[0].name == "spider1"
        assert response.items[1].name == "spider2"

    def test_spider_list_response_empty_list(self):
        """SpiderListResponse 可以包含空列表"""
        response = SpiderListResponse(items=[], total=0)

        assert response.items == []
        assert response.total == 0


class TestRunItem:
    """测试 RunItem 模型"""

    def test_run_item_has_all_required_fields(self):
        """RunItem 包含 id、spider_name、started_at、finished_at、status、item_count、error_message、duration_ms"""
        now = datetime.now(timezone.utc)
        run = RunItem(
            id=1,
            spider_name="hackernews",
            started_at=now,
            finished_at=now,
            status="success",
            item_count=50,
            error_message=None,
            duration_ms=1000,
        )

        assert run.id == 1
        assert run.spider_name == "hackernews"
        assert run.started_at == now
        assert run.finished_at == now
        assert run.status == "success"
        assert run.item_count == 50
        assert run.error_message is None
        assert run.duration_ms == 1000

    def test_run_item_optional_fields_can_be_none(self):
        """RunItem 的可选字段（finished_at、error_message、duration_ms）可以为 None"""
        now = datetime.now(timezone.utc)
        run = RunItem(
            id=2,
            spider_name="test_spider",
            started_at=now,
            finished_at=None,
            status="running",
            item_count=0,
            error_message=None,
            duration_ms=None,
        )

        assert run.finished_at is None
        assert run.error_message is None
        assert run.duration_ms is None
        assert run.status == "running"

    def test_run_item_serializes_datetime_to_utc_iso(self):
        """RunItem datetime 字段序列化为 ISO 8601 UTC 格式"""
        now = datetime.now(timezone.utc)
        run = RunItem(
            id=3,
            spider_name="test",
            started_at=now,
            finished_at=now,
            status="failed",
            item_count=0,
            error_message="Connection timeout",
            duration_ms=5000,
        )

        data = run.model_dump(mode="json")
        assert "started_at" in data
        assert "finished_at" in data
        # ISO 8601 格式检查
        assert data["started_at"].endswith("Z") or "+" in data["started_at"]
        assert data["finished_at"].endswith("Z") or "+" in data["finished_at"]


class TestRunListResponse:
    """测试 RunListResponse 模型"""

    def test_run_list_response_has_items_and_total(self):
        """RunListResponse 包含 items 数组和 total 整数"""
        now = datetime.now(timezone.utc)
        items = [
            RunItem(
                id=1,
                spider_name="test",
                started_at=now,
                finished_at=now,
                status="success",
                item_count=100,
                error_message=None,
                duration_ms=1000,
            ),
            RunItem(
                id=2,
                spider_name="test",
                started_at=now,
                finished_at=None,
                status="running",
                item_count=0,
                error_message=None,
                duration_ms=None,
            ),
        ]

        response = RunListResponse(items=items, total=2)

        assert len(response.items) == 2
        assert response.total == 2

    def test_run_list_response_empty_list(self):
        """RunListResponse 可以包含空列表"""
        response = RunListResponse(items=[], total=0)

        assert response.items == []
        assert response.total == 0


class TestTriggerResponse:
    """测试 TriggerResponse 模型"""

    def test_trigger_response_has_message_and_run_id(self):
        """TriggerResponse 包含 message 和 run_id 字段"""
        response = TriggerResponse(message="Spider started successfully", run_id=123)

        assert response.message == "Spider started successfully"
        assert response.run_id == 123

    def test_trigger_response_can_have_different_message_formats(self):
        """TriggerResponse 的 message 可以是任意字符串"""
        response1 = TriggerResponse(message="Triggered", run_id=1)
        response2 = TriggerResponse(message="采集任务已启动", run_id=2)
        response3 = TriggerResponse(message="", run_id=3)

        assert response1.message == "Triggered"
        assert response2.message == "采集任务已启动"
        assert response3.message == ""
