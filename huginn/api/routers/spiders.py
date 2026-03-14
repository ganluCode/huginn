"""Spider 管理相关 API 路由

提供 Spider 列表、详情、触发运行等接口。
"""

import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.api.deps import get_db_session
from huginn.api.schemas import (
    RunListResponse,
    SpiderDetail,
    SpiderItem,
    SpiderListResponse,
    TriggerResponse,
)
from huginn.core.models import SpiderRegistry, SpiderRun

__all__ = ["router"]

router = APIRouter()


@router.get("/spiders", response_model=SpiderListResponse)
async def list_spiders(
    category: str | None = None,
    enabled: bool | None = None,
    db_session: AsyncSession | None = Depends(get_db_session),
) -> SpiderListResponse:
    """获取 Spider 列表

    支持按 category 和 enabled 筛选，按 created_at DESC 排序。

    Args:
        category: 可选，按 category 筛选
        enabled: 可选，按 enabled 筛选
        db_session: 数据库 session（依赖注入）

    Returns:
        SpiderListResponse: 包含 items 列表和 total 总数
    """
    if db_session is None:
        # 数据库不可用，返回空列表
        return SpiderListResponse(items=[], total=0)

    # 构建查询
    query = select(SpiderRegistry)

    # 应用筛选条件
    if category is not None:
        query = query.where(SpiderRegistry.category == category)
    if enabled is not None:
        query = query.where(SpiderRegistry.enabled == enabled)

    # 排序
    query = query.order_by(SpiderRegistry.created_at.desc())

    # 执行查询
    result = await db_session.execute(query)
    spiders = result.scalars().all()

    # 转换为响应模型
    items = [SpiderItem.model_validate(spider) for spider in spiders]

    return SpiderListResponse(items=items, total=len(items))


@router.get("/spiders/{name}", response_model=SpiderDetail)
async def get_spider_detail(
    name: str,
    db_session: AsyncSession | None = Depends(get_db_session),
) -> SpiderDetail:
    """获取 Spider 详情

    根据 Spider 名称查询详情，包含 config 字段。

    Args:
        name: Spider 名称
        db_session: 数据库 session（依赖注入）

    Returns:
        SpiderDetail: Spider 详情（包含 config 字段）

    Raises:
        HTTPException: Spider 不存在时返回 404
    """
    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spider '{name}' not found",
        )

    # 查询 Spider
    query = select(SpiderRegistry).where(SpiderRegistry.name == name)
    result = await db_session.execute(query)
    spider = result.scalar_one_or_none()

    if spider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spider '{name}' not found",
        )

    return SpiderDetail.model_validate(spider)


@router.post("/spiders/{name}/run", response_model=TriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_spider_run(
    name: str,
    db_session: AsyncSession | None = Depends(get_db_session),
) -> TriggerResponse:
    """触发 Spider 运行

    校验 Spider 存在、未在运行，然后非阻塞启动 Scrapy 进程。

    Args:
        name: Spider 名称
        db_session: 数据库 session（依赖注入）

    Returns:
        TriggerResponse: 包含消息和运行 ID

    Raises:
        HTTPException: Spider 不存在时返回 404，正在运行时返回 409
    """
    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spider '{name}' not found",
        )

    # 1. 校验 Spider 存在
    query = select(SpiderRegistry).where(SpiderRegistry.name == name)
    result = await db_session.execute(query)
    spider = result.scalar_one_or_none()

    if spider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spider '{name}' not found",
        )

    # 2. 校验未在运行（查询 spider_runs 表中是否有 status=running 的记录）
    running_query = select(SpiderRun).where(
        SpiderRun.spider_name == name,
        SpiderRun.status == "running",
    )
    running_result = await db_session.execute(running_query)
    existing_run = running_result.scalar_one_or_none()

    if existing_run is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Spider '{name}' is already running",
        )

    # 3. 在 spider_runs 插入 running 记录
    run = SpiderRun(
        spider_name=name,
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db_session.add(run)
    await db_session.flush()

    # 4. 非阻塞启动 scrapy crawl {name}
    subprocess.Popen(
        ["scrapy", "crawl", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 5. 返回 202 响应
    return TriggerResponse(
        message=f"Spider '{name}' started successfully",
        run_id=run.id,
    )
