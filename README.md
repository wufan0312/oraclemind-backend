# 玄镜 OracleMind 后端服务

Python + FastAPI 后端骨架（排盘计算服务方向），与前端 `oraclemind/`（Next.js 14）配套。

> 技术选型依据 `tech_stack_plan.html`：排盘服务用 Python FastAPI（天文历法库生态：sxtwl / lunar-python），
> 业务 / AI 解读 / 用户 / 支付服务后续按规划接入 Node.js 侧。

## 目录结构

```
oraclemind-backend/
├── app/
│   ├── main.py            # FastAPI 应用工厂 + 生命周期
│   ├── core/              # 配置（pydantic-settings）与日志
│   ├── db/                # SQLAlchemy 2.0 async 引擎 / 会话 / Base
│   ├── models/            # ORM 模型（用户/排盘/报告等，规划见 tech_stack_plan §5）
│   ├── schemas/           # Pydantic 请求/响应模型
│   ├── api/
│   │   ├── router.py      # API 总路由
│   │   └── v1/            # v1 版本路由（health / ping / 后续术数接口）
│   └── services/          # 业务逻辑层（排盘算法、AI 编排等按模块扩展）
├── docker-compose.yml     # 本地开发依赖：PostgreSQL 16 + Redis 7
├── pyproject.toml
└── .env.example           # 环境变量模板（复制为 .env）
```

## 快速启动

```bash
# 1. 启动本地依赖（PostgreSQL + Redis；本机已装有对应服务可跳过）
docker compose up -d

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -e ".[dev]"

# 3. 准备环境变量
cp .env.example .env

# 4. 启动服务
uvicorn app.main:app --reload --port 8000
```

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（含 PostgreSQL / Redis 连接状态） |
| GET | `/api/v1/ping` | 连通性示例路由 |
| **POST** | **`/api/v1/numerology/paipan`** | **数字命理排盘（生命灵数 / 九宫格 / 流年）** |
| GET | `/docs` | Swagger 交互式文档 |
| GET | `/openapi.json` | OpenAPI 规范 |

### 数字命理排盘示例

```bash
curl -s -X POST http://localhost:8000/api/v1/numerology/paipan \
  -H "Content-Type: application/json" \
  -d '{"year":1995,"month":5,"day":18}' | python -m json.tool
```

响应字段与前端 `computeNum` 输出完全对齐（`lifePath`/`birthdayNum`/`counts`/`missing`/`years`/`data`）。

健康检查返回 `200`（全部就绪）或 `503`（依赖降级，服务本身仍在运行）：

```json
{
  "status": "ok",
  "app": "玄镜 OracleMind 后端",
  "version": "0.1.0",
  "database": "up",
  "redis": "up"
}
```

## 约定

- 数据库连接失败不阻断服务启动，降级状态由 `/api/health` 反映（`database: "down"`）。
- 路由统一挂在 `/api` 前缀下，版本化路由放 `api/v1/`。
- 后续模块（八字/紫微/六爻/梅花/奇门排盘、AI 解读编排）在 `services/` 下按模块新增，接口在 `api/v1/` 扩展。
=======

