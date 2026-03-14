"""常量定义测试"""

from huginn.core.constants import Category, EngineType, SpiderStatus


class TestCategoryEnum:
    """测试 Category 枚举"""

    def test_has_all_expected_values(self):
        """Category 应包含 tech/social/finance/market/news 五个值"""
        assert Category.TECH.value == "tech"
        assert Category.SOCIAL.value == "social"
        assert Category.FINANCE.value == "finance"
        assert Category.MARKET.value == "market"
        assert Category.NEWS.value == "news"

    def test_string_comparison_works(self):
        """StrEnum 应支持直接字符串比较"""
        assert Category.TECH == "tech"
        assert Category.SOCIAL == "social"
        assert Category.TECH != "social"

    def test_all_category_values(self):
        """遍历所有 Category 值应为 5 个"""
        values = {c.value for c in Category}
        assert values == {"tech", "social", "finance", "market", "news"}
        assert len(Category) == 5


class TestSpiderStatusEnum:
    """测试 SpiderStatus 枚举"""

    def test_has_all_expected_values(self):
        """SpiderStatus 应包含 running/success/failed 三个值"""
        assert SpiderStatus.RUNNING.value == "running"
        assert SpiderStatus.SUCCESS.value == "success"
        assert SpiderStatus.FAILED.value == "failed"

    def test_string_comparison_works(self):
        """StrEnum 应支持直接字符串比较"""
        assert SpiderStatus.RUNNING == "running"
        assert SpiderStatus.SUCCESS == "success"
        assert SpiderStatus.RUNNING != "failed"

    def test_all_status_values(self):
        """遍历所有 SpiderStatus 值应为 3 个"""
        values = {c.value for c in SpiderStatus}
        assert values == {"running", "success", "failed"}
        assert len(SpiderStatus) == 3


class TestEngineTypeEnum:
    """测试 EngineType 枚举"""

    def test_has_all_expected_values(self):
        """EngineType 应包含 scrapy/rpa 两个值"""
        assert EngineType.SCRAPY.value == "scrapy"
        assert EngineType.RPA.value == "rpa"

    def test_string_comparison_works(self):
        """StrEnum 应支持直接字符串比较"""
        assert EngineType.SCRAPY == "scrapy"
        assert EngineType.RPA == "rpa"
        assert EngineType.SCRAPY != "rpa"

    def test_all_engine_values(self):
        """遍历所有 EngineType 值应为 2 个"""
        values = {c.value for c in EngineType}
        assert values == {"scrapy", "rpa"}
        assert len(EngineType) == 2
