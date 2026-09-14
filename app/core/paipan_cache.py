"""排盘结果缓存：参数不变 → 命中内存缓存直接返回，不重算。

补齐后端排盘层的结果缓存，对齐 AI 服务（oraclemind-ai-py）已有的响应缓存能力。
采用进程内内存 LRU（带 TTL 与容量淘汰），不依赖 Redis：
- Redis 当前在本机常处于 down（降级模式），内存缓存已能避免重复重算；
- 重启后端后缓存清空，下次同参数自动重建（前端另有 localStorage 缓存兜底）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("paipan_cache")

# 30 天 TTL：排盘结果（同公历出生信息）长期恒定
_TTL_SECONDS = 30 * 24 * 3600
_MAX_ENTRIES = 2000

_MEM: dict[str, tuple[float, Any]] = {}


def _make_key(namespace: str, req_dict: dict) -> str:
    raw = namespace + "|" + json.dumps(
        req_dict, sort_keys=True, ensure_ascii=False, default=str
    )
    return "paipan:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _evict() -> None:
    now = time.time()
    expired = [k for k, (ts, _) in _MEM.items() if now - ts >= _TTL_SECONDS]
    for k in expired:
        _MEM.pop(k, None)
    if len(_MEM) > _MAX_ENTRIES:
        # 保留最近一半（最旧在前）
        items = sorted(_MEM.items(), key=lambda kv: kv[1][0])
        keep = dict(items[len(items) // 2:])
        _MEM.clear()
        _MEM.update(keep)


async def cached_paipan(
    namespace: str,
    req_dict: dict,
    compute: Callable[[], Any],
) -> tuple[Any, bool]:
    """参数不变 → 命中缓存直接返回，不重算。返回 (result, from_cache)。

    compute 为同步 CPU 计算函数（排盘服务均为同步返回 dict）。
    P1 修复（S6）：用 ``asyncio.to_thread`` 将同步计算移出事件循环，
    避免排盘这类重 CPU 任务阻塞整个 asyncio 事件循环、拖垮其他并发请求。
    """
    key = _make_key(namespace, req_dict)
    now = time.time()

    hit = _MEM.get(key)
    if hit is not None and now - hit[0] < _TTL_SECONDS:
        logger.info("[paipan-cache] hit=true ns=%s", namespace)
        return hit[1], True

    val = await asyncio.to_thread(compute)
    _MEM[key] = (now, val)
    if len(_MEM) > _MAX_ENTRIES:
        _evict()
    logger.info("[paipan-cache] hit=false ns=%s", namespace)
    return val, False
