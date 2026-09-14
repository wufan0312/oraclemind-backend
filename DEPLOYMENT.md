# 部署指南：dev SQLite / staging·prod PostgreSQL

玄镜后端已支持一套代码双数据层：**本地开发用 SQLite（零配置），staging/prod 用 PostgreSQL**。
切换只靠环境变量 `DATABASE_URL`，无需改代码。

---

## 1. 关键约束（务必先读）

> ⚠️ **Vercel 上绝不能用 SQLite。**
> Vercel 的函数实例是临时只读文件系统，SQLite 文件会在每次部署/冷启动后丢失，且多实例不共享。
> 因此：**任何部署到 Vercel 的环境，DATABASE_URL 必须指向外部托管的 PostgreSQL。**
> 代码已内置防呆：当 `APP_ENV=production` 或检测到 `VERCEL=1` 且仍用 SQLite 时，`init_db()`
> 会直接抛 `RuntimeError` 阻止启动（不会被容错逻辑吞掉）。

---

## 2. 数据层切换表

| 环境 | `APP_ENV` | `DATABASE_URL` | 说明 |
|------|-----------|----------------|------|
| 本地 dev | `development` | `sqlite+aiosqlite:///./oraclemind.db` | 零配置，文件即库 |
| staging/prod | `production` | `postgresql+asyncpg://user:pass@host:5432/db?ssl=require` | 外部托管 PG |

`DATABASE_URL` 优先级：环境变量 > `.env`。Vercel 项目设置的 Environment Variables 会覆盖 `.env`。

> ⚠️ **SSL 参数必须用 `ssl=require`，不是 `sslmode=require`。**
> 运行时驱动是 **asyncpg**，它只认 `ssl`（如 `?ssl=require`）；而 `sslmode` 是 psycopg2/libpq 的
> 参数，asyncpg 收到 `sslmode` 会直接报错。构建期的 `alembic upgrade head` 走 psycopg2，
> `migrations/env.py` 会自动把 `ssl=*` 转成 `sslmode=*`，所以你只需在 `DATABASE_URL` 里写
> `?ssl=require` 即可，两层都能通。

---

## 3. 迁移（Alembic）

schema 由 Alembic 管理（`migrations/`），已生成 baseline `48b6c8479c7d`。

- **开发（SQLite）**：首次启动 `init_db()` 会自动 `alembic upgrade head`，无需手动。
- **生产（PG）**：在部署流程里**对 PG 执行一次** `alembic upgrade head` 建表。
  - 本地对 PG 跑：`DATABASE_URL='postgresql+asyncpg://...' alembic upgrade head`
  - Vercel：把该命令放进 **Build Command** 或在 CI/CD 中跑一次（PG 是外部库，幂等、可重复）。
- 查看状态：`alembic current` / `alembic history`
- 回滚：`alembic downgrade -1`

> 现有本地 SQLite 数据不会自动迁移到 PG。如需迁移，见第 5 节。

---

## 4. Vercel 环境变量清单（prod）

在 Vercel 项目 Settings → Environment Variables 设置（Production / Preview 分开）：

| 变量 | 值 |
|------|----|
| `DATABASE_URL` | `postgresql+asyncpg://...`（PG 连接串，asyncpg 驱动）|
| `REDIS_URL` | `rediss://...`（Vercel 上的 Redis 走 TLS，如 Upstash）|
| `JWT_SECRET` | 强随机 |
| `ENCRYPTION_KEY` | `Fernet.generate_key()` 产物（P0-4 敏感加密，必填）|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |

---

## 5. 现有 SQLite 数据迁移到 PG（可选，一次性）

若需把本地已有 `oraclemind_run.db` 导入新 PG：

1. 在 PG 上建表：`DATABASE_URL='postgresql+asyncpg://...' alembic upgrade head`
2. 写一个一次性导出/导入脚本（建议用 SQLAlchemy 全表 `bulk_insert`，注意 `birth` 等已加密字段原样搬运）。
3. 验证行数一致后切换 `.env` / Vercel 的 `DATABASE_URL`。

> 此脚本为一次性工具，未纳入常驻迁移（Alembic 只管 schema，不管数据搬运）。

---

## 6. 后端上 Vercel（已实现 serverless 化 · 原生 ASGI）

> ⚠️ **方案已纠正**：Vercel 2026 对 Python **原生支持 ASGI**（FastAPI/Flask/Django 自动识别），
> 直接加载 ASGI 应用运行，**不再需要 Mangum**。早期 Mangum 方案已废弃（且 Mangum 0.22 无 Vercel handler，
> 在 Vercel 上无法正确解析事件）。当前 `api/index.py` 直接 `from app.main import app` 暴露 `app`，由
> `pyproject.toml` 的 `[tool.vercel] entrypoint = "api.index:app"` 锁定入口。

### 工件

| 文件 | 作用 |
|------|------|
| `api/index.py` | `from app.main import app` —— 直接暴露 FastAPI ASGI 应用，Vercel 原生驱动 |
| `pyproject.toml` | `[tool.vercel] entrypoint = "api.index:app"` 锁定 Vercel 入口 |
| `requirements.txt` | **精选**运行时依赖（fastapi/sqlalchemy/alembic/asyncpg/aiosqlite/redis/cryptography/PyJWT/passlib/lunar-python 等），供 Vercel 安装 |
| `vercel.json` | 函数 `maxDuration=60, memory=1024` + `excludeFiles`（剔除 .venv/tests/脚本等，缩小包体） |

### 路由前缀（权威结论：不会双 /api，router 的 /api 前缀保留不动）

- 前端调用 `https://<backend-project>.vercel.app/api/v1/numerology/paipan`。
- Vercel 把 `/api/*` 路由到 `api/index.py`，并把**完整路径（含 /api）**交给 FastAPI ASGI 应用。
- 后端 `app/api/router.py` 注册的也是 `/api` 前缀（`api_router = APIRouter(prefix="/api")`），
  与 Vercel 传入的路径天然对齐 → **无需任何前缀改造，也不存在双 /api**。
- 前端 `NEXT_PUBLIC_API_BASE` 填「后端域名根路径，**不含 /api**」（如 `https://x.vercel.app`），
  `/api/v1/...` 由 `src/lib/api.ts` 的请求路径携带。若把 `/api` 写进 base，才会造成双 `/api`。

### 数据库迁移（Alembic）—— 推荐在 Build Command 跑（最稳）

1. **Build Command**（推荐，幂等、可靠）：`alembic upgrade head`
   在 Vercel 项目 Settings → Build & Development Settings 设置；需 `DATABASE_URL`(PG) 作为
   build 环境变量（Production/Preview 分开配）。PG 建表一次性完成，不依赖冷启动。
2. **lifespan 兜底**：应用启动钩子仍会调 `init_db()` → `alembic upgrade head`，首次冷启动自动对齐
   schema（并发冷启动靠 `alembic_version` 表幂等，低风险）。
3. 只需在 Vercel 环境变量配好 `DATABASE_URL`（`postgresql+asyncpg://...`）。

### 推荐部署形态：后端独立 Vercel 项目

- 在 Vercel 把该项目的 `rootDirectory` 设为 `oraclemind-backend`。
- 环境变量（Production / Preview 分开）：

  | 变量 | 值 |
  |------|----|
  | `DATABASE_URL` | `postgresql+asyncpg://...`（外部托管 PG，必填）|
  | `REDIS_URL` | `rediss://...`（Vercel 上 Redis 走 TLS，如 Upstash）|
  | `JWT_SECRET` | 强随机 |
  | `ENCRYPTION_KEY` | `Fernet.generate_key()` 产物（P0-4 敏感加密，必填）|
  | `APP_ENV` | `production` |
  | `DEBUG` | `false` |
  | `CORS_ORIGINS` | 加前端域名，如 `https://oraclemind.vercel.app`（逗号分隔，支持多环境）|

- 前端 `NEXT_PUBLIC_API_BASE` 指向 `https://<backend-project>.vercel.app`（不含 /api）。

### 体积评估（500MB 限制）—— 已规避

- Vercel Python 函数包体上限为 **500MB 未压缩**（Fluid compute 可到 5GB），远比早期 250MB 宽松。
- 本机 venv 344MB 的大头是 `cv2`/`numpy`/`PIL`/`mypy` 等**与后端无关**的包（`app/` 未 import），
  不会进入部署包。`vercel.json` 的 `excludeFiles` 进一步剔除 `.venv/tests/backups/scripts/*.py`。
- `requirements.txt` 为**精选列表**，部署包约 60–120MB，远低于上限。**切勿**用 `pip freeze` 整份 venv。

### 本地验证结果（已通过）

- `from api.index import app` 可导入（顶层 ASGI 应用，Vercel 入口）。
- `TestClient` 命中 `GET /api/health` → `200`，`database: up / redis: up`。
- ASGI 路由前缀与本地完全一致（`/api/health`、`/api/v1/...` 均 200）。

### 首次部署必查

- **冷启动耗时**：`lunar-python` 等导入在冷启动会多几秒；`maxDuration=60` 已留余量，若仍超时
  可上调或依赖瘦身。Pro 版可用 Warm Functions 预热。
- **长驻假设**：当前无（DB 连接池 + `pool_pre_ping`、Redis asyncio client 均 serverless 友好）；
  若有定时任务/后台线程需另接 Vercel Cron 或外部队列。
- **10s 超时（Hobby）**：Hobby 计划函数上限 10s，排盘类接口若偶发超时请升级 Pro（60s）。
- **NEXT_PUBLIC_* 构建时注入**：前端改 `NEXT_PUBLIC_API_BASE` 后必须重新部署前端，仅改 Vercel
  环境变量不够（Next.js 在 build 时固化这些值）。
