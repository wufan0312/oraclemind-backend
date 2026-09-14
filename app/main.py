"""玄镜 OracleMind 后端入口 —— FastAPI 应用工厂。

启动：
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.init_db import init_db
from app.db.session import check_database, check_redis, close_connections

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：建表 → 启动探活（不阻断），退出时释放连接。"""
    setup_logging()
    logger.info("正在启动 %s v%s (env=%s)", settings.app_name, settings.app_version, settings.app_env)
    await init_db()
    db_up = await check_database()
    redis_up = await check_redis()
    logger.info("启动探活 -> PostgreSQL: %s | Redis: %s", "up" if db_up else "down", "up" if redis_up else "down")
    yield
    await close_connections()
    logger.info("服务已退出，连接已释放")


def create_app() -> FastAPI:
    """应用工厂：便于测试时以不同配置创建实例。"""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="玄镜 OracleMind 后端服务（排盘计算 / AI 编排方向）",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # CORS —— 允许前端 Next.js 开发/生产地址
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # P1 修复（S7）：全局未处理异常处理器 —— 记录完整 traceback 并返回合法 JSON 500，
    # 消除「SQL 已提交却返回 500 且无 traceback」的幽灵错误（响应序列化/意外异常均被捕获）。
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        getLogger(__name__).error(
            "未处理异常 %s %s: %s", request.method, request.url.path, exc, exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试。"},
        )

    # P1 修复（S3）：反代信任 —— 仅当 proxy_trusted=true（部署在可信反代后）才启用，
    # 信任 X-Forwarded-* 头；默认关闭避免客户端伪造协议/来源。配合生产强制 Cookie secure。
    if settings.proxy_trusted:
        from starlette.middleware.proxy_headers import ProxyHeadersMiddleware

        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    # 业务路由统一挂 /api 前缀（见 api/router.py）
    app.include_router(api_router)

    @app.get("/", summary="服务信息")
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
