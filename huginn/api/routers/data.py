"""数据查询相关 API 路由

提供采集数据的查询、统计、导出等接口。
"""

import asyncio
import csv
import json
from datetime import UTC, datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, field_serializer

from huginn.core.storage import PostgresBackend

__all__ = ["router"]

router = APIRouter()

# ============================================================================
# 请求模型（Pydantic schemas）
# ============================================================================


def parse_datetime_iso(value: str) -> datetime:
    """解析 ISO 8601 格式的 datetime 字符串

    用于 FastAPI 查询参数的自定义解析器。

    Args:
        value: ISO 8601 格式的 datetime 字符串

    Returns:
        datetime 对象

    Raises:
        ValueError: 格式无效时
    """
    try:
        # 尝试解析带时区的 ISO 格式
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # 转换为 UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {value}. Use ISO 8601 format (e.g., 2024-01-01T00:00:00Z)") from e


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


# ============================================================================
# 端点实现
# ============================================================================


@router.get("", response_model=DataListResponse)
async def query_data(
    source: str | None = Query(default=None, description="按数据源过滤"),
    category: str | None = Query(default=None, description="按分类过滤"),
    keyword: str | None = Query(default=None, description="关键词搜索"),
    time_from: str | None = Query(default=None, description="起始时间 (ISO 8601)"),
    time_to: str | None = Query(default=None, description="结束时间 (ISO 8601)"),
    limit: int = Query(default=50, ge=1, description="每页条数，默认 50"),
    offset: int = Query(default=0, ge=0, description="偏移量，默认 0"),
) -> DataListResponse:
    """查询采集数据

    支持按 source、category、keyword、time_from、time_to 过滤，支持分页。

    Args:
        source: 按数据源过滤
        category: 按分类过滤
        keyword: 关键词搜索（在 title 或 data 字段中）
        time_from: 起始时间（ISO 8601 格式）
        time_to: 结束时间（ISO 8601 格式）
        limit: 每页条数，默认 50，最大截断为 200
        offset: 偏移量，默认 0
        db_session: 数据库 session（依赖注入）

    Returns:
        DataListResponse: 包含 items 列表、total 总数、limit、offset

    Raises:
        ValueError: time_from 或 time_to 格式无效时
    """
    # 截断 limit 最大为 200
    limit = min(limit, 200)

    # 解析时间参数
    parsed_time_from: datetime | None = None
    parsed_time_to: datetime | None = None

    if time_from is not None:
        try:
            parsed_time_from = parse_datetime_iso(time_from)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    if time_to is not None:
        try:
            parsed_time_to = parse_datetime_iso(time_to)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    # 创建存储后端
    backend = PostgresBackend()

    # 并行查询数据和总数
    items, total = await asyncio.gather(
        backend.query(
            source=source,
            category=category,
            keyword=keyword,
            time_from=parsed_time_from,
            time_to=parsed_time_to,
            limit=limit,
            offset=offset,
        ),
        backend.count(
            source=source,
            category=category,
            keyword=keyword,
            time_from=parsed_time_from,
            time_to=parsed_time_to,
        ),
    )

    # 转换为响应模型
    return DataListResponse(
        items=[DataItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sources", response_model=SourceListResponse)
async def get_sources() -> SourceListResponse:
    """获取数据源列表

    返回按 total_count DESC 排序的数据源列表。

    Returns:
        SourceListResponse: 包含数据源摘要列表
    """
    backend = PostgresBackend()
    sources = await backend.get_sources_summary()

    # 转换为响应模型
    return SourceListResponse(
        items=[SourceSummary(**s) for s in sources]
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    days: int = Query(default=7, ge=0, description="统计最近几天数据，0 表示仅统计今天"),
) -> StatsResponse:
    """获取数据统计

    返回按 source、category、date 分组的统计数据。

    Args:
        days: 统计最近几天数据，默认 7，0 表示仅统计今天

    Returns:
        StatsResponse: 包含 total、by_source、by_category、by_date 的统计
    """
    backend = PostgresBackend()
    stats = await backend.get_stats(days=days)

    # 转换为响应模型
    return StatsResponse(
        total=stats["total"],
        by_source=[StatsBySource(**s) for s in stats["by_source"]],
        by_category=[StatsByCategory(**c) for c in stats["by_category"]],
        by_date=[StatsByDate(**d) for d in stats["by_date"]],
    )


@router.get("/export")
async def export_data(
    source: str | None = Query(default=None, description="按数据源过滤"),
    category: str | None = Query(default=None, description="按分类过滤"),
    keyword: str | None = Query(default=None, description="关键词搜索"),
    time_from: str | None = Query(default=None, description="起始时间 (ISO 8601)"),
    time_to: str | None = Query(default=None, description="结束时间 (ISO 8601)"),
    format: str = Query(default="json", description="导出格式: csv 或 json"),
):
    """导出采集数据

    支持与 /api/data 相同的筛选参数，使用 StreamingResponse 流式输出。
    最多导出 10000 条数据。

    Args:
        source: 按数据源过滤
        category: 按分类过滤
        keyword: 关键词搜索
        time_from: 起始时间（ISO 8601 格式）
        time_to: 结束时间（ISO 8601 格式）
        format: 导出格式，"csv" 或 "json"

    Returns:
        StreamingResponse: 流式输出的 CSV 或 JSON 文件

    Raises:
        ValueError: format 不是 "csv" 或 "json" 时
        ValueError: time_from 或 time_to 格式无效时
    """
    # 验证 format 参数
    if format not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid format: {format}. Must be 'csv' or 'json'",
        )

    # 解析时间参数
    parsed_time_from: datetime | None = None
    parsed_time_to: datetime | None = None

    if time_from is not None:
        try:
            parsed_time_from = parse_datetime_iso(time_from)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    if time_to is not None:
        try:
            parsed_time_to = parse_datetime_iso(time_to)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    # 限制最大导出数量为 10000
    max_export_limit = 10000

    # 创建存储后端
    backend = PostgresBackend()

    # 查询数据
    items = await backend.query(
        source=source,
        category=category,
        keyword=keyword,
        time_from=parsed_time_from,
        time_to=parsed_time_to,
        limit=max_export_limit,
        offset=0,
    )

    # 根据 format 返回不同的响应
    if format == "csv":
        # CSV 格式
        output = StringIO(newline="")

        def generate_csv():
            """生成 CSV 内容的生成器"""
            # 写入表头
            writer = csv.writer(output)
            writer.writerow(["id", "source", "category", "collected_at", "title", "url", "data"])

            # 写入数据行
            for item in items:
                data = item["data"]
                title = data.get("title", "")
                url = data.get("url", "")
                # 将 data 字段序列化为 JSON 字符串
                data_json = json.dumps(data, ensure_ascii=False)

                writer.writerow([
                    item["id"],
                    item["source"],
                    item["category"],
                    item["collected_at"],
                    title,
                    url,
                    data_json,
                ])

            # 返回内容
            output.seek(0)
            yield output.read()
            output.close()

        filename = f"huginn_data_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }

        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers=headers,
        )

    else:  # format == "json"
        # JSON 格式
        def generate_json():
            """生成 JSON 内容的生成器"""
            yield json.dumps(items, ensure_ascii=False, indent=2)

        filename = f"huginn_data_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }

        return StreamingResponse(
            generate_json(),
            media_type="application/json",
            headers=headers,
        )
