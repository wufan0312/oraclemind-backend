"""统一日志配置 —— 结构化输出，方便后续接入 Prometheus / 日志采集。"""

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


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
    root.setLevel(settings.log_level.upper())
    root.addHandler(handler)

    # 降低第三方库噪音
    for noisy in ("uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取带模块名的业务日志器。"""
    return logging.getLogger(name)
