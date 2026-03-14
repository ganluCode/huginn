"""Spider 管理相关 API 路由

提供 Spider 列表、详情、触发运行等接口。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.api.deps import get_db_session
from huginn.api.schemas import SpiderDetail, SpiderItem, SpiderListResponse
from huginn.core.models import SpiderRegistry

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
