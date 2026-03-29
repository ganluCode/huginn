"""关键词监控管理 API 路由

提供关键词监控配置的查询、新增和删除接口。
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.api.deps import get_db_session
from huginn.core.models import KeywordMonitor

__all__ = ["router"]

router = APIRouter()


class MonitorItem(BaseModel):
    """关键词监控响应模型"""

    id: int
    keyword: str
    sources: list[str] | None = None
    enabled: bool
    webhook_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_datetime_to_utc(self, dt: datetime | None) -> str | None:
        """将 datetime 序列化为 ISO 8601 UTC 格式（带 Z 后缀）"""
        if dt is None:
            return None
        dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        return dt.isoformat().replace("+00:00", "Z")


class MonitorCreate(BaseModel):
    """创建关键词监控请求模型"""

    keyword: str
    sources: list[str] | None = None
    enabled: bool = True
    webhook_url: str | None = None

    @field_validator("keyword")
    @classmethod
    def keyword_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("keyword must not be empty")
        return v


@router.get("/monitors", response_model=list[MonitorItem])
async def list_monitors(
    db_session: AsyncSession | None = Depends(get_db_session),
) -> list[MonitorItem]:
    """获取关键词监控列表

    Args:
        db_session: 数据库 session（依赖注入）

    Returns:
        list[MonitorItem]: 关键词监控列表，按 created_at DESC 排序
    """
    if db_session is None:
        return []

    query = select(KeywordMonitor).order_by(KeywordMonitor.created_at.desc())
    result = await db_session.execute(query)
    monitors = result.scalars().all()

    return [MonitorItem.model_validate(m) for m in monitors]


@router.post("/monitors", response_model=MonitorItem, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    body: MonitorCreate,
    db_session: AsyncSession | None = Depends(get_db_session),
) -> MonitorItem:
    """创建关键词监控

    Args:
        body: 创建请求体（keyword 不能为空）
        db_session: 数据库 session（依赖注入）

    Returns:
        MonitorItem: 新建的监控对象

    Raises:
        HTTPException: 数据库不可用时返回 503
    """
    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    monitor = KeywordMonitor(
        keyword=body.keyword,
        sources=body.sources,
        enabled=body.enabled,
        webhook_url=body.webhook_url,
        created_at=datetime.now(UTC),
    )
    db_session.add(monitor)
    await db_session.flush()

    return MonitorItem.model_validate(monitor)


@router.delete("/monitors/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: int,
    db_session: AsyncSession | None = Depends(get_db_session),
) -> None:
    """删除关键词监控

    Args:
        monitor_id: 监控 ID
        db_session: 数据库 session（依赖注入）

    Raises:
        HTTPException: 不存在时返回 404，数据库不可用时返回 404
    """
    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor {monitor_id} not found",
        )

    query = select(KeywordMonitor).where(KeywordMonitor.id == monitor_id)
    result = await db_session.execute(query)
    monitor = result.scalar_one_or_none()

    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor {monitor_id} not found",
        )

    await db_session.delete(monitor)
