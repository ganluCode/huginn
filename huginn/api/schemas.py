"""FastAPI 响应模型（Pydantic v2 schemas）

定义 API 响应的 Pydantic 模型，用于序列化和数据验证。
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_serializer

# Spider 相关响应模型


class SpiderItem(BaseModel):
    """Spider 列表项响应模型

    包含 Spider 的基本信息，用于列表展示。
    """

    name: str
    engine: str
    category: str | None = None
    schedule: str | None = None
    enabled: bool
    last_run_at: datetime | None = None
    last_status: str | None = None
    item_count: int
    created_at: datetime

    # 配置 ORM 兼容（可以从 SQLAlchemy 模型创建）
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_run_at", "created_at")
    def serialize_datetime_to_utc(self, dt: datetime | None) -> str | None:
        """将 datetime 序列化为 ISO 8601 UTC 格式（带 Z 后缀）"""
        if dt is None:
            return None
        # 确保 datetime 有时区信息，转换为 UTC
        dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        # 返回带 Z 后缀的 ISO 格式
        return dt.isoformat().replace("+00:00", "Z")


class SpiderDetail(SpiderItem):
    """Spider 详情响应模型

    继承 SpiderItem 的所有字段，额外包含 config 字段。
    """

    config: dict | None = None


class SpiderListResponse(BaseModel):
    """Spider 列表响应模型

    包含 Spider 列表和总数。
    """

    items: list[SpiderItem]
    total: int


# Spider 运行记录相关响应模型


class RunItem(BaseModel):
    """Spider 运行记录响应模型

    包含单次运行的详细信息。
    """

    id: int
    spider_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    item_count: int
    error_message: str | None = None
    duration_ms: int | None = None

    # 配置 ORM 兼容
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "finished_at")
    def serialize_datetime_to_utc(self, dt: datetime | None) -> str | None:
        """将 datetime 序列化为 ISO 8601 UTC 格式（带 Z 后缀）"""
        if dt is None:
            return None
        # 确保 datetime 有时区信息，转换为 UTC
        dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        # 返回带 Z 后缀的 ISO 格式
        return dt.isoformat().replace("+00:00", "Z")


class RunListResponse(BaseModel):
    """运行记录列表响应模型

    包含运行记录列表和总数。
    """

    items: list[RunItem]
    total: int


# Spider 触发运行响应模型


class TriggerResponse(BaseModel):
    """Spider 触发运行响应模型

    返回触发结果消息和运行 ID。
    """

    message: str
    run_id: int
