# 玄镜 OracleMind · 后端服务层

这是 OracleMind（玄镜）的后端服务层。

OracleMind 是一套已上线的生产级 AI 平台，前端、AI 服务、后端三端解耦。本仓库是整套系统的**确定性计算底座**：八字 / 紫微 / 六爻 / 梅花 / 奇门 / 数字命理 / 占星等排盘与历法计算都在这里用代码完成，AI 服务只负责在算好的结果上做解读。

如果你在找「能把不确定的东西变确定、知道哪些事根本不该交给模型」的人，这个仓库和 AI 服务层那套降级设计，是同一个判断的两个侧面。

---

## 这块解决什么问题

- **排盘算不准，比不排更糟**：命理 / 占星的干支、星历、宫位全是确定性计算，差一天、差一度结论就变。交给模型「大概算一下」，结果不可复现、无法审计。
- **多端各算各的，结果对不上**：Web、小程序、管理后台、AI 服务如果各自实现排盘，迟早出现「同一生日前后端结论不一致」的事故。
- **Serverless 下数据库连接容易炸**：Vercel 函数冷启动、连接池、长连接这些问题，处理不好就是间歇性 500。
- **出生信息等敏感数据不能裸存**：用户的生辰是高度敏感信息，明文落库既不安全也不合规。

---

## 核心设计决策

### 1. 确定性计算不放给模型——AI 调我，而不是我调模型

排盘 / 历法全部用天文历法库（`lunar-python` 等）在 Python 里确定性算出，结果可复现、可缓存、可单测。

> 这条和 AI 服务层是同一句话的两面：AI 服务把「算」抽成 tool 调我，我这边绝不碰模型。整个产品里，**凡是能由代码 100% 算对的，就不让模型参与**——模型只生成候选解读，系统代码负责校验和兜底。

### 2. 异步 SQLAlchemy 2.0 + PG / Redis，并为 Serverless 重建

- 异步驱动（`asyncpg`）+ 连接池带 `pool_pre_ping`，serverless 冷启动下不会拿到死连接。
- Vercel 2026 已原生支持 ASGI，直接加载 `api/index.py`（`from app.main import app`），**不再需要 Mangum**；函数 `maxDuration=60 / memory=1024`，`vercel.json` 用 `excludeFiles` 剔除非运行文件缩小包体。
- 切换环境只靠 `DATABASE_URL` 一个变量，本地 SQLite、线上 Neon PostgreSQL 同一套 SQLAlchemy 模型，零代码改动。

### 3. 数据库连接失败，不让服务起不来

`/api/health` 在 DB / Redis 不可用时返回 `database: down` / `redis: down`，**服务本身照常运行**，而不是启动即崩。排盘是纯计算、不依赖 DB，断库时核心能力仍可用；依赖 DB 的接口再优雅降级。

### 4. 敏感数据加密 + 审计

用户生辰等敏感字段用 `ENCRYPTION_KEY`（Fernet）加密落库，JWT 鉴权，关键操作留审计日志。密钥走环境变量，绝不入库。

---

## 怎么跑起来

### 环境要求

- Python 3.12+
- 本地依赖：PostgreSQL 16 + Redis 7（`docker compose up -d` 一键起）
- 运行时依赖是**精选**的（`requirements.txt`，切勿 `pip freeze` 整份导出）
- 生产数据库必须是外部托管的 PostgreSQL（`DATABASE_URL` 指向 asyncpg 连接串），Vercel 函数不提供本地 DB

### 安装与启动

```bash
cd oraclemind-backend
docker compose up -d                                  # 起 PostgreSQL + Redis

python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
alembic upgrade head                                 # 在 PG 上建表（首次）

uvicorn app.main:app --reload --port 8000            # 本地开发
```

健康检查：

```bash
curl -s http://localhost:8000/api/health
# { "status": "ok", "database": "up", "redis": "up" }
```

### 环境变量示例

```bash
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/oraclemind
REDIS_URL=redis://localhost:6379
JWT_SECRET=<强随机>
ENCRYPTION_KEY=<Fernet.generate_key() 产物>    # 必填，敏感字段加密
```

### 部署（Vercel）

独立 Vercel 项目，`Root Directory = oraclemind-backend`，原生 ASGI 入口 `api/index.py`。部署前在环境变量配好 `DATABASE_URL`（PG）/ `REDIS_URL`（Upstash，走 `rediss://`）/ `JWT_SECRET` / `ENCRYPTION_KEY`，并执行 `alembic upgrade head` 建表。冷启动因 `lunar-python` 导入会多几秒，`maxDuration=60` 已留余量。详见 `DEPLOYMENT.md`。
