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
  只需在 Vercel 项目环境变量里配好 DATABASE_URL（支持 postgres:// 裸 scheme，会自动补成 asyncpg）。

启动期崩溃兜底（重要）：
- Serverless 环境下，**import 期**抛出的异常只会得到 HTTP 500 + `X-Vercel-Error:
  FUNCTION_INVOCATION_FAILED`，响应体是 Vercel 的固定文案，看不到任何 traceback。
- 曾因此长时间无法定位「DATABASE_URL 填了裸 postgres:// 导致异步驱动不匹配」这类问题。
- 这里捕获 import 异常并降级成一个同样响应 ASGI 的「启动失败应用」，把所有请求返回
  `{"error": "BOOT_ERROR", ...}`，把异常类型、消息（已脱敏）与最后几行堆栈直接吐出来，
  `curl` 一次即可定位。正式修复后本分支不会命中。
- 脱敏：连接串里的 `//user:password@` 一律替换为 `//***:***@`，避免把数据库口令泄漏到公网。
"""

from __future__ import annotations

import json
import os
import re
import traceback
from typing import Any

# 连接串脱敏：postgres://user:pass@host → postgres://***:***@host
_SECRET_IN_URL = re.compile(r"(?P<scheme>[a-zA-Z0-9+.\-]+://)(?P<user>[^:/@\s]+):(?P<pw>[^@/\s]*)@")


def _redact(text: str) -> str:
    """抹掉可能出现在异常消息里的数据库口令。"""
    return _SECRET_IN_URL.sub(lambda m: f"{m.group('scheme')}***:***@", text)


def _build_boot_error_app(exc: BaseException) -> Any:
    """构造一个「启动失败」的 ASGI 应用，让 500 也有可读 body。"""

    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    # 只保留最后 6 行：足以定位出错文件与语句，又不至于把整个依赖栈铺到公网
    tail = "".join(tb_lines[-6:]).strip()
    payload = {
        "error": "BOOT_ERROR",
        "message": "后端在导入阶段崩溃，应用未能启动（详见 type/detail/traceback）。",
        "type": type(exc).__name__,
        "detail": _redact(str(exc))[:500],
        "traceback": _redact(tail)[:1500],
        "hint": [
            "1) DATABASE_URL 必须是 postgresql+asyncpg://...（postgres:// 裸前缀会自动补全，但值不能为空或仍是 sqlite）",
            "2) ENCRYPTION_KEY 必须是 44 字符的 url-safe base64（Fernet）；JWT_SECRET 不能是 change-me-in-production",
            "3) Vercel 面板改完变量后必须手动 Redeploy，否则运行时拿到的还是旧值",
        ],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode()),
        # 允许任意来源：仅为了让浏览器/curl 都能看到启动错误（此时没有正常服务可谈安全边界）
        (b"access-control-allow-origin", b"*"),
        (b"cache-control", b"no-store"),
    ]

    async def _boot_error_app(scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "lifespan":
            # 必须正确应答 lifespan，否则 ASGI 服务器会认为启动失败并直接掐掉进程
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        await send({"type": "http.response.start", "status": 500, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return _boot_error_app


try:
    from app.main import app  # noqa: E402 - 必须在 _build_boot_error_app 定义之后
except Exception as _boot_exc:  # noqa: BLE001 - 任何导入期异常都要转成可读 500
    # 同时打到 stdout，方便在 Vercel → Observability / Runtime Logs 里检索
    print("[BOOT_ERROR] 后端导入阶段失败：", _redact("".join(
        traceback.format_exception(type(_boot_exc), _boot_exc, _boot_exc.__traceback__)
    )), flush=True)
    app = _build_boot_error_app(_boot_exc)  # type: ignore[assignment]

# 方便在 /health 之外快速确认环境变量是否被平台注入（仅类型/前缀，不含值）
if os.environ.get("VERCEL") == "1":
    print(
        "[BOOT] VERCEL=1, APP_ENV=%s, DATABASE_URL 前缀=%s"
        % (os.environ.get("APP_ENV"), (os.environ.get("DATABASE_URL") or "").split("://")[0] or "<未设置>"),
        flush=True,
    )

# Vercel 加载的 ASGI 应用入口（顶层 app 变量）。
__all__ = ["app"]
