"""数据查询相关 API 路由

提供采集数据的查询、统计、导出等接口。
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, field_serializer

__all__ = ["router"]

router = APIRouter()


# ============================================================================
# 响应模型（Pydantic schemas）
# ============================================================================


class DataItem(BaseModel):
    """单条采集数据响应模型

    包含 id、source、category、collected_at、data 字段。
    """

    id: int
    source: str
    category: str
    collected_at: str  # ISO 8601 UTC 格式字符串
    data: dict

    # 配置 ORM 兼容
    model_config = ConfigDict(from_attributes=True)


class DataListResponse(BaseModel):
    """数据列表响应模型

    包含数据列表和总数，以及分页信息。
    """

    items: list[DataItem]
    total: int
    limit: int
    offset: int


class StatsBySource(BaseModel):
    """按 source 分组的统计项"""

    source: str
    count: int


class StatsByCategory(BaseModel):
    """按 category 分组的统计项"""

    category: str
    count: int


class StatsByDate(BaseModel):
    """按 date 分组的统计项"""

    date: str  # YYYY-MM-DD 格式
    count: int


class StatsResponse(BaseModel):
    """数据统计响应模型

    包含 total、by_source、by_category、by_date 四个维度的统计。
    """

    total: int
    by_source: list[StatsBySource]
    by_category: list[StatsByCategory]
    by_date: list[StatsByDate]


class SourceSummary(BaseModel):
    """数据源摘要响应模型

    包含 source、category、total_count、latest_at 字段。
    """

    source: str
    category: str
    total_count: int
    latest_at: str | None  # ISO 8601 UTC 格式字符串，无数据时为 None


class SourceListResponse(BaseModel):
    """数据源列表响应模型

    包含数据源摘要列表。
    """

    items: list[SourceSummary]
