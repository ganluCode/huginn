"""Spider 管理相关 API 路由

提供 Spider 列表、详情、触发运行等接口。
"""

from fastapi import APIRouter

__all__ = ["router"]

router = APIRouter()
