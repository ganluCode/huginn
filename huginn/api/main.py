"""FastAPI 应用主入口

创建并配置 FastAPI 应用实例。
"""

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from huginn.api.deps import get_db_session, get_redis
from huginn.core.exceptions import HuginnError

__all__ = ["app"]

app = FastAPI(title="Huginn API")

# 配置 CORS 中间件，允许前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HuginnError 异常处理器
@app.exception_handler(HuginnError)
async def huginn_error_handler(_request: Request, exc: HuginnError) -> JSONResponse:
    """处理 HuginnError 及其子类异常，返回 JSON 格式的错误响应

    Args:
        request: FastAPI 请求对象
        exc: HuginnError 异常实例

    Returns:
        JSONResponse: 包含 detail 字段的 JSON 响应
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


# 创建 API 路由，挂载到 /api 前缀
api_router = APIRouter()


@api_router.get("/health")
async def health_check(
    db_session=Depends(get_db_session),
    redis=Depends(get_redis),
):
    """健康检查端点

    检查 PostgreSQL 和 Redis 连接状态，返回服务健康状态。
    即使某个依赖服务不可用，接口仍返回 200 和 status=ok，
    但会在响应中标注具体服务的状态。

    Returns:
        dict: 包含 status、postgres、redis 三个字段的响应

    Response example:
        {
            "status": "ok",
            "postgres": true,
            "redis": true
        }
    """
    postgres_ok = False
    redis_ok = False

    # 检查 PostgreSQL 连接
    try:
        result = await db_session.execute(text("SELECT 1"))
        result.scalar_one()
        postgres_ok = True
    except Exception:
        postgres_ok = False

    # 检查 Redis 连接
    if redis is not None:
        try:
            redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    return {
        "status": "ok",
        "postgres": postgres_ok,
        "redis": redis_ok,
    }


# 导入并注册路由到 api_router
from huginn.api.routers import data, monitors, spiders  # noqa: E402

api_router.include_router(spiders.router)
api_router.include_router(data.router, prefix="/data")
api_router.include_router(monitors.router)

# 将 API 路由挂载到 /api 前缀
app.include_router(api_router, prefix="/api")
