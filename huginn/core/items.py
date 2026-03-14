"""数据类定义：CollectedItem 和 CollectTask

定义了项目核心数据结构：
- CollectedItem: 采集结果数据项
- CollectTask: 采集任务
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CollectedItem:
    """采集结果数据项

    表示从数据源采集到的一条数据。

    Attributes:
        source: 数据源标识（如 "hackernews", "weibo_hot"）
        category: 数据分类（tech/social/finance/market/news）
        data: 业务数据，自由格式的字典
        collected_at: 采集时间，默认为当前 UTC 时间
    """

    source: str
    category: str
    data: dict
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CollectTask:
    """采集任务

    表示一个待执行的采集任务。

    Attributes:
        source: 数据源标识
        engine: 采集引擎类型（scrapy/rpa）
        schedule: cron 表达式
        config: 引擎特定配置，默认为空字典
    """

    source: str
    engine: str
    schedule: str
    config: dict = field(default_factory=dict)
