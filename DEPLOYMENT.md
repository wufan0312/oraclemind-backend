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

---

## 7. Vercel 部署实战排障记录（2026-09-14 全量复盘）

以下为首次把本后端部署到 Vercel 时逐个踩过的坑，**按出现顺序**记录。每一关都已修复并验证，
可作为后续部署/他人排障的对照表。

### 0. 前置铁律（先读，能挡掉 80% 的坑）

| 项 | 说明 |
|----|------|
| 变量必须勾 **Production 档** | Vercel 变量分 Production / Preview / Development 三档。部署是 production 环境，某变量没勾 Production 档 → 运行时取不到 → 落回代码默认值。本次多个崩溃本质是「变量没进 Production 运行时」而非代码 bug。 |
| 改动 env 必须重新部署 | Vercel 改环境变量**不会热更**运行时。需基于最新 commit 重新 build，或改 env 后弹窗的 Redeploy（会重建并带新 env）。对旧部署快照点 Redeploy 不生效。 |
| 本地访问需代理 | Vercel 域名在国内常被墙，本机直连可能 `ERR_CONNECTION_TIMED_OUT`（TCP 层就超时，非应用崩溃）。务必开代理 / 换网络 / 用在线探测工具验证。 |
| 不能填空值 | Vercel 面板某变量设为空串，会覆盖代码默认值（如 `LOG_LEVEL`、`REDIS_URL` 被存成空 → 启动崩溃）。要么填实际值，要么干脆不设这个变量让它用默认。 |

### 关卡速查表

| # | 阶段 | 现象 | 根因 | 修复位置 |
|---|------|------|------|----------|
| ① | Build（alembic） | `invalid dsn: invalid connection option "ssl"` | `DATABASE_URL` 里的 `?ssl=require` 是 asyncpg 写法；构建期 `alembic` 走 psycopg2，只认 `sslmode` | `migrations/env.py` 的 `_sync_url` 自动 `ssl→sslmode` 转换 + 丢弃 asyncpg 专用参数 |
| ② | Build（alembic） | `column "is_active" is of type boolean but expression is of type integer` | 迁移原始 SQL 给布尔列写整数字面量 `1`/`0`，PG 不允许 integer 隐转 boolean | `d2a1f3c5e6b7_admin_system.py`（`is_active` `1→TRUE`）、`f1a2b3c4d5e6_community.py`（`is_pinned` `0→FALSE`）|
| ③ | Runtime 启动 | `FUNCTION_INVOCATION_FAILED`（无具体堆栈） | 初判 ENCRYPTION_KEY 缺失，**实际**是 `DATABASE_URL` 没进 Production 运行时 → `validate_for_runtime()` 检测到 SQLite 拒绝启动 | 在 Vercel 把 `DATABASE_URL` 等变量勾 Production 档 + 重新部署 |
| ④ | Runtime 导入 | `ValueError: Redis URL must specify one of the following schemes` | `REDIS_URL` 填了非法值（空串/占位符），`Redis.from_url` 在 import 阶段即崩溃 | `app/db/session.py` 包 try/except，非法 URL 回退占位 Redis（缓存走内存兜底）|
| ⑤ | Runtime 启动 | `ValueError: Unknown level: ''` | `LOG_LEVEL` 被存成空串，`root.setLevel('')` 崩溃 | `app/core/config.py` 给 `log_level` 加 validator 回退 `INFO`；`app/core/logging.py` 加 try/except 兜底 |
| ⑥ | 本地访问 | `ERR_CONNECTION_TIMED_OUT` | 本机网络到 Vercel 被墙，非代码问题 | 开代理 / 换网络 / 用在线探测 |

### 各关详情

#### ① Build 期 alembic：`ssl` 参数不被 psycopg2 接受
- 构建跑 `vercel.json` 的 `buildCommand: alembic upgrade head`，Alembic 用**同步驱动 psycopg2**。
- `DATABASE_URL` 写成 `postgresql+asyncpg://...?ssl=require`，`ssl=require` 是 asyncpg 参数；psycopg2/libpq 只认 `sslmode` → `invalid dsn`。
- **修复**：`migrations/env.py` 的 `_sync_url` 在切到 psycopg2 时把 `ssl=*` 改写成 `sslmode=*`，并丢弃 asyncpg 专用参数（`prepared_statement_cache_size` / `statement_cache_size` / `prepared_statement_name_func`，psycopg2 同样不认）。
- 运行时（asyncpg）不受影响，继续写 `?ssl=require` 即可。

#### ② Build 期 alembic：布尔列整数字面量
- PG **不允许** integer 隐式转 boolean，但**字符串** `'1'`/`'0'` 可以（所以 `server_default='1'` 建表没问题）。
- 会崩的是**裸 SQL INSERT 里的数值字面量**：`is_active` 写 `1`、`is_pinned` 写 `0`。
- **修复**：改成 `TRUE` / `FALSE`（PG 与 SQLite 都认，可移植）。
- 排查方法：全量 grep `migrations/versions` 里的 `op.execute` / `INSERT INTO`，确认仅此两处真布尔字面量（其余 `server_default='1'` 是字符串，安全）。

#### ③ Runtime：`FUNCTION_INVOCATION_FAILED`（无堆栈）
- 第一次看到时误判为「缺 ENCRYPTION_KEY」（`app/core/crypto.py` 生产无密钥会在 import 期 `raise`）。
- 用户反馈变量一直设着，遂搭本地隔离 venv 做真实导入复现：
  - 生产 env 全配上 → `import api.index` → **IMPORT OK**（代码无导入期崩溃）
  - 仅撤掉 `DATABASE_URL` → 启动即崩，报错 `RuntimeError: 生产/Vercel 环境检测到 SQLite database_url，已阻止启动`
- **真因**：构建环境有 `DATABASE_URL`、运行时没有 → 落回 SQLite 默认 → `validate_for_runtime()` 拒绝启动。
- **判据（可复用）**：`FUNCTION_INVOCATION_FAILED` + 构建期 migrations 正常 = 运行时 env 缺失导致 SQLite 兜底。直接 `import api.index` 配齐/撤变量复现，比猜日志更准。

#### ④ Runtime：`REDIS_URL` 非法导致 import 崩溃
- 默认值 `redis://localhost:6379/0` 合法，因此必然是 Vercel 面板把 `REDIS_URL` 设成了非法值（空串/占位符）。
- `app/db/session.py` 原本在**模块级** `redis_client = Redis.from_url(settings.redis_url, ...)`，import 阶段解析即抛 `ValueError`。
- **修复**：改为 `_build_redis_client()`，try/except 包住；非法 URL 回退 `Redis(host="localhost", port=0, ...)` 占位实例，仅 warning。`redis_service.py` 调用层已捕获连接异常走内存缓存，import 不崩即可。
- 验证：`REDIS_URL=false` 下 `import api.index` → `IMPORT_OK`（warning 后正常）。

#### ⑤ Runtime：`log_level` 空串导致启动崩溃
- `log_level` 默认 `"INFO"`，运行时被取为空串（与 ④ 同类：面板存空值）→ `root.setLevel('')` 抛 `ValueError`。
- **修复（两层）**：
  1. `app/core/config.py` 给 `log_level` 加 `field_validator`：空/非法值回退 `INFO`。
  2. `app/core/logging.py` 对 `root.setLevel` 加 try/except 兜底 `INFO`。
- 验证：`LOG_LEVEL=""` 下 `setup_logging()` 不崩，level=20(INFO)。

#### ⑥ 本地访问超时（非代码）
- 部署 `Ready Latest` 后，浏览器/本机 `curl` 均 `CONNECTION_TIMED_OUT`（http_code 000）。
- 这是**网络层**到 Vercel 不通（国内墙），与代码无关。开代理 / 换网络 / 在线探测工具即可访问。
- 注意区分：`CONNECTION_TIMED_OUT`（TCP 层没连上）= 网络问题；`FUNCTION_INVOCATION_FAILED` 或 JSON 500 = 应用问题。

### 本次改动清单（均需 commit + push 到 `oraclemind-backend` 才生效）

- `migrations/env.py` — `_sync_url` ssl→sslmode 转换 + 丢弃 asyncpg 专用参数
- `migrations/versions/d2a1f3c5e6b7_admin_system.py` — `is_active` 字面量 `1→TRUE`
- `migrations/versions/f1a2b3c4d5e6_community.py` — `is_pinned` 字面量 `0→FALSE`
- `app/db/session.py` — `REDIS_URL` 非法时 import 期不崩溃
- `app/core/config.py` — `log_level` 空值回退 INFO
- `app/core/logging.py` — `root.setLevel` 兜底
- `DEPLOYMENT.md` — 本排障章节 + 第 2 节 SSL 参数说明

> ⚠️ 构建机从 `github.com/wufan0312/oraclemind-backend` 重新 clone，本地改动不自动生效。
> 推上去后基于最新 commit 重新部署即可。
