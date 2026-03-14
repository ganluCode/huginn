"""FastAPI 应用主入口

创建并配置 FastAPI 应用实例。
"""

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
async def huginn_error_handler(request: Request, exc: HuginnError) -> JSONResponse:
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
async def health_check():
    """健康检查端点

    返回基本的健康状态，用于验证服务是否正常运行。
    后续可以扩展为检查数据库、Redis 等依赖服务的状态。
    """
    return {"status": "ok"}


# 将 API 路由挂载到 /api 前缀
app.include_router(api_router, prefix="/api")
