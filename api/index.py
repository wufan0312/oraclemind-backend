"""Vercel 入口：直接把 FastAPI ASGI 应用暴露给 Vercel 的 Python 运行时。

部署形态（后端作为独立 Vercel 项目，rootDirectory=oraclemind-backend）：
- 本文件位于 api/index.py，Vercel 自动将其作为 Python ASGI Function 入口（tool.vercel.entrypoint=api.index:app）。
- Vercel 2026 原生支持 ASGI，**无需 Mangum**：它直接加载本模块的 `app` 变量并以 ASGI 协议驱动，
  本地跑的 FastAPI 应用「原样」部署上线。
- 前端调用 https://<backend-project>.vercel.app/api/... 即命中本应用。

路由前缀说明（避免双 /api）：
- Vercel 把 `/api/*` 请求路由到 api/index.py，并把完整路径（含 /api）交给 FastAPI。
- 本应用 router 注册的也是 `/api` 前缀（见 app/api/router.py: api_router = APIRouter(prefix="/api")），
  因此 /api/health 这类路径在 Vercel 上与本地完全一致，**无需任何前缀改造，也不会出现双 /api**。

数据库迁移（Alembic）：
- 推荐在 Build Command 里跑一次 `alembic upgrade head`（PG 已建表，幂等）。
- 同时应用 lifespan 启动钩子也会调用 init_db() -> alembic upgrade head 作为兜底（首次冷启动自动对齐 schema）。
  只需在 Vercel 项目环境变量里配好 DATABASE_URL（postgresql+asyncpg://...）。
"""

from app.main import app

# Vercel 加载的 ASGI 应用入口（顶层 app 变量）。
__all__ = ["app"]
