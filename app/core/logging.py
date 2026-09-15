"""统一日志配置 —— 结构化输出，方便后续接入 Prometheus / 日志采集。"""

import logging
import re
import sys

from app.core.config import settings

_CONFIGURED = False

# 连接串脱敏：postgres://user:pw@host → postgres://***:***@host
_SECRET_IN_URL = re.compile(
    r"(?P<scheme>[a-zA-Z0-9+.\-]+://)(?P<user>[^:/@\s]+):(?P<pw>[^@/\s]*)@"
)


def redact_secrets(text: str) -> str:
    """抹掉文本中可能出现的数据库口令/带凭证 URL，用于安全地对外暴露错误详情。

    启动期错误经常把 DATABASE_URL 原样带进异常消息（asyncpg 连接失败的提示里就有），
    直接打进 JSON 响应会把口令泄漏到公网，统一在这里过一道。
    """
    return _SECRET_IN_URL.sub(lambda m: f"{m.group('scheme')}***:***@", text)


def setup_logging() -> None:
    """初始化根日志器（幂等）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    level_name = (settings.log_level or "INFO").upper()
    try:
        root.setLevel(level_name)
    except ValueError:  # pragma: no cover - 防御：非法级别回退 INFO
        root.setLevel(logging.INFO)
    root.addHandler(handler)

    # 降低第三方库噪音
    for noisy in ("uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取带模块名的业务日志器。"""
    return logging.getLogger(name)
