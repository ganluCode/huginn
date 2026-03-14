"""SQLAlchemy 模型行为测试"""

import pytest
from sqlalchemy.exc import IntegrityError

from huginn.core.models import CollectedData, SpiderRegistry, SpiderRun


class TestCollectedDataComputedColumns:
    """测试 CollectedData 生成列行为"""

    def test_title_and_url_from_data(self, db_session):
        """插入含 title 和 url 的数据，生成列应正确提取"""
        item = CollectedData(
            source="test",
            category="test",
            data={"title": "Hello", "url": "https://x.com"}
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.title == "Hello"
        assert item.url == "https://x.com"

    def test_title_and_url_null_when_missing(self, db_session):
        """插入不含 title 和 url 的数据，生成列应为 None"""
        item = CollectedData(
            source="test",
            category="test",
            data={"score": 100}
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.title is None
        assert item.url is None


class TestSpiderRegistryPrimaryKey:
    """测试 SpiderRegistry 主键约束"""

    def test_duplicate_name_raises_integrity_error(self, db_session):
        """重复插入相同 name 的记录应抛出 IntegrityError"""
        spider1 = SpiderRegistry(
            name="test_spider",
            engine="scrapy",
            category="test"
        )
        db_session.add(spider1)
        db_session.commit()

        # 尝试插入相同 name
        spider2 = SpiderRegistry(
            name="test_spider",  # 重复
            engine="rpa",
            category="test"
        )
        db_session.add(spider2)

        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSpiderRunForeignKey:
    """测试 SpiderRun 外键约束"""

    def test_invalid_spider_name_raises_integrity_error(self, db_session):
        """spider_name 引用不存在的 Spider 应抛出 IntegrityError"""
        # 不先创建 SpiderRegistry，直接插入 SpiderRun
        run = SpiderRun(
            spider_name="nonexistent_spider",
            status="running"
        )
        db_session.add(run)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_valid_spider_name_succeeds(self, db_session):
        """spider_name 引用存在的 Spider 应成功"""
        # 先创建 SpiderRegistry
        spider = SpiderRegistry(
            name="test_spider",
            engine="scrapy",
            category="test"
        )
        db_session.add(spider)
        db_session.commit()

        # 再插入 SpiderRun
        run = SpiderRun(
            spider_name="test_spider",
            status="running"
        )
        db_session.add(run)
        db_session.commit()

        assert run.id is not None
