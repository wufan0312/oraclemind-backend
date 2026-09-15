"""玄镜 OracleMind 后端入口 —— FastAPI 应用工厂。

启动：
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from logging import getLogger
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, redact_secrets, setup_logging
from app.db.init_db import init_db
from app.db.session import check_database, check_redis, close_connections

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：建表 → 启动探活（不阻断），退出时释放连接。

    ⚠️ 启动期异常一律「捕获后挂到 app.state.boot_error」，不允许冒泡。
    Serverless（Vercel）里 lifespan.startup 抛异常会让函数**进程级崩溃**，
    对外只剩一个没有 body 的 500 `FUNCTION_INVOCATION_FAILED`，连原因都看不到
    （本项目为此白耗了一整轮排查）。捕获后由 `_boot_error_guard` 中间件把请求
    变成 503 + 可读 JSON，`curl` 一次即可定位；同时异常仍带 traceback 打进 stdout。
    """
    setup_logging()
    app.state.boot_error = None
    try:
        logger.info(
            "正在启动 %s v%s (env=%s)",
            settings.app_name,
            settings.app_version,
            settings.app_env,
        )
        await init_db()
        db_up = await check_database()
        redis_up = await check_redis()
        logger.info(
            "启动探活 -> PostgreSQL: %s | Redis: %s",
            "up" if db_up else "down",
            "up" if redis_up else "down",
        )
    except Exception as exc:  # noqa: BLE001 - 启动失败必须可诊断，不能进程级崩溃
        app.state.boot_error = exc
        logger.error(
            "启动失败，服务进入诊断模式（所有请求返回 503）：%s",
            redact_secrets(str(exc)),
            exc_info=True,
        )

    yield

    try:
        await close_connections()
    except Exception as exc:  # noqa: BLE001 - 退出阶段的异常不该影响进程收尾
        logger.warning("关闭连接时异常：%s", exc)
    logger.info("服务已退出，连接已释放")



def _add_proxy_headers_middleware(app: FastAPI) -> None:
    """挂载 ProxyHeadersMiddleware，兼容 Starlette 1.x 的模块搬迁。

    ⚠️ 这里踩过一个**生产级**的坑：`starlette.middleware.proxy_headers` 在 Starlette
    1.0 已被移除（改由 uvicorn 提供）。requirements.txt 里 fastapi 是 `>=0.115.0`
    的宽松约束，线上会装到最新版 → 该 import 在 `create_app()` 执行期直接 ImportError。
    因为 `proxy_trusted` 只有**生产**（.env.production 的 PROXY_TRUSTED=true）才为真，
    本地开发永远走不到这行，于是表现为「本地一切正常、线上冷启动必崩」，
    且 Vercel 只回一个没有 body 的 500。故改为多路径探测 + 失败仅告警。
    """
    candidates = (
        "uvicorn.middleware.proxy_headers",  # Starlette 1.x 的正解
        "starlette.middleware.proxy_headers",  # 老版本 Starlette
    )
    last_error: Exception | None = None
    for module_path in candidates:
        try:
            module = __import__(module_path, fromlist=["ProxyHeadersMiddleware"])
            app.add_middleware(module.ProxyHeadersMiddleware, trusted_hosts="*")
            return
        except Exception as exc:  # noqa: BLE001 - 逐个候选尝试，全失败则降级
            last_error = exc
    logger.warning(
        "ProxyHeadersMiddleware 不可用（%s），已跳过 X-Forwarded-* 信任；"
        "影响：request.url.scheme 在反代后可能为 http。",
        last_error,
    )


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
        _add_proxy_headers_middleware(app)

    # 启动失败守卫：lifespan 没跑完（boot_error 非空）时，把所有请求变成 503 + 可读 JSON。
    #
    # 为什么需要它：Serverless 里 lifespan.startup 抛异常 = 函数进程级崩溃，外部只能看到
    # Vercel 的固定文案 500 FUNCTION_INVOCATION_FAILED（无 body），排查全靠翻 Runtime Logs。
    # 有了它，`curl https://<backend>/api/health` 就能直接看到原因类型与最后几行堆栈。
    #
    # 安全：仍然返回 503 **拒绝提供任何业务能力**，因此不会退化成「生产悄悄跑 SQLite」；
    # 详情里的连接串口令由 redact_secrets 统一脱敏。
    # 注意：本中间件比 CORS 更靠外（Starlette 后注册者更外层），故手动补一次 CORS 头，
    # 否则浏览器端只会看到跨域错误、看不到这段诊断信息。
    @app.middleware("http")
    async def _boot_error_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        boot_error = getattr(app.state, "boot_error", None)
        if boot_error is None:
            return await call_next(request)

        tb_tail = "".join(
            traceback.format_exception(type(boot_error), boot_error, boot_error.__traceback__)[-6:]
        ).strip()
        headers: dict[str, str] = {}
        origin = request.headers.get("origin")
        if origin and origin in settings.cors_origin_list:
            headers["access-control-allow-origin"] = origin
            headers["vary"] = "Origin"

        return JSONResponse(
            status_code=503,
            headers=headers,
            content={
                "error": "BOOT_ERROR",
                "message": (
                    "后端未完成启动（503 诊断模式）。请按下方 detail 修正 Vercel 面板的"
                    "环境变量，然后 Redeploy（改环境变量不会自动触发部署）。"
                ),
                "type": type(boot_error).__name__,
                "detail": redact_secrets(str(boot_error))[:600],
                "traceback": redact_secrets(tb_tail)[:1500],
                "hint": [
                    "DATABASE_URL 必须是 postgresql+asyncpg://...（裸 postgres:// 会自动补驱动，但值不能为空/不能是 sqlite）",
                    "JWT_SECRET 不能为空，也不能是源码里的占位符 change-me-in-production",
                    "ENCRYPTION_KEY 支持 44 字符 url-safe base64 或 64 位 hex（两种都会自动归一化）",
                    "改完环境变量必须手动 Redeploy，运行时才会拿到新值",
                ],
            },
        )

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
