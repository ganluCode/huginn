"""数据类测试：CollectedItem 和 CollectTask"""

from datetime import datetime, timezone

import pytest

from huginn.core.items import CollectTask, CollectedItem


class TestCollectedItem:
    """测试 CollectedItem 数据类"""

    def test_create_with_required_fields(self):
        """CollectedItem 使用必填字段应创建成功"""
        item = CollectedItem(source="test", category="tech", data={})
        assert item.source == "test"
        assert item.category == "tech"
        assert item.data == {}

    def test_collected_at_default_is_utc_aware(self):
        """CollectedItem 未传 collected_at 时应自动填充 UTC 时区感知的 datetime"""
        item = CollectedItem(source="test", category="tech", data={})
        assert isinstance(item.collected_at, datetime)
        assert item.collected_at.tzinfo is not None
        assert item.collected_at.tzinfo == timezone.utc

    def test_source_empty_string_allowed(self):
        """CollectedItem source 为空字符串时应允许创建"""
        item = CollectedItem(source="", category="tech", data={})
        assert item.source == ""

    def test_data_empty_dict_allowed(self):
        """CollectedItem data 为空 dict 时应允许创建"""
        item = CollectedItem(source="test", category="tech", data={})
        assert item.data == {}

    def test_collected_at_can_be_overridden(self):
        """CollectedItem collected_at 可以手动指定"""
        custom_time = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)
        item = CollectedItem(
            source="test", category="tech", data={}, collected_at=custom_time
        )
        assert item.collected_at == custom_time

    def test_data_can_contain_arbitrary_fields(self):
        """CollectedItem data 可以包含任意字段"""
        item = CollectedItem(
            source="hackernews", category="tech", data={"title": "Test", "score": 100}
        )
        assert item.data["title"] == "Test"
        assert item.data["score"] == 100


class TestCollectTask:
    """测试 CollectTask 数据类"""

    def test_create_with_required_fields(self):
        """CollectTask 使用必填字段应创建成功"""
        task = CollectTask(source="test", engine="scrapy", schedule="*/5 * * * *")
        assert task.source == "test"
        assert task.engine == "scrapy"
        assert task.schedule == "*/5 * * * *"

    def test_config_default_is_empty_dict(self):
        """CollectTask config 默认值应为空字典"""
        task = CollectTask(source="test", engine="scrapy", schedule="*/5 * * * *")
        assert task.config == {}

    def test_config_instances_are_independent(self):
        """两个不同 CollectTask 实例的 config 默认值应互相独立"""
        task1 = CollectTask(source="test1", engine="scrapy", schedule="*/5 * * * *")
        task2 = CollectTask(source="test2", engine="scrapy", schedule="*/5 * * * *")

        task1.config["key1"] = "value1"
        task2.config["key2"] = "value2"

        assert task1.config == {"key1": "value1"}
        assert task2.config == {"key2": "value2"}
        assert "key2" not in task1.config
        assert "key1" not in task2.config

    def test_config_can_be_provided(self):
        """CollectTask config 可以手动指定"""
        custom_config = {"timeout": 30, "retries": 3}
        task = CollectTask(
            source="test", engine="scrapy", schedule="*/5 * * * *", config=custom_config
        )
        assert task.config == custom_config

    def test_config_custom_is_independent_from_default(self):
        """手动指定的 config 应与默认值互不影响"""
        task1 = CollectTask(source="test1", engine="scrapy", schedule="*/5 * * * *")
        task2 = CollectTask(
            source="test2", engine="scrapy", schedule="*/5 * * * *", config={"key": "value"}
        )

        task1.config["default_key"] = "default_value"
        task2.config["key2"] = "value2"

        assert task1.config == {"default_key": "default_value"}
        assert task2.config == {"key": "value", "key2": "value2"}
