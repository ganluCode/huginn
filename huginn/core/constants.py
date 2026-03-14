"""常量定义：数据源分类、Spider 状态、引擎类型"""

from enum import StrEnum


class Category(StrEnum):
    """数据源分类"""

    TECH = "tech"
    SOCIAL = "social"
    FINANCE = "finance"
    MARKET = "market"
    NEWS = "news"


class SpiderStatus(StrEnum):
    """Spider 运行状态"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class EngineType(StrEnum):
    """采集引擎类型"""

    SCRAPY = "scrapy"
    RPA = "rpa"
