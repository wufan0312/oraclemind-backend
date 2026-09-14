"""Redis 业务层 —— JWT 黑名单 / 接口限流 / 迁移互斥锁。

设计原则（与项目既有降级哲学一致）：
- **Redis 是增强，不是依赖**：任何 Redis 异常都降级为「放行」，绝不阻断主流程；
- 进程内保留一份轻量兜底状态，Redis 短暂不可用时功能不塌方；
- 所有 key 统一前缀 `oj:`（oraclemind），格式 `oj:{scope}:{entity}:{id}`：

    ===============  =============  ==================================
    key 模式          TTL            用途
    ===============  =============  ==================================
    oj:bl:jwt:{jti}  token 剩余寿命  登出 / 改密后使旧 token 立即失效
    oj:rl:{ip}:{mi}  120s           登录注册等敏感接口的固定窗口限流
    oj:lock:vis:{v}  30s            访客数据迁移互斥锁（防并发重复认领）
    ===============  =============  ==================================

Redis 不可用时：
- 黑名单 → 内存 set（单进程有效，重启丢失，可接受）；
- 限流   → 内存计数器（单进程有效）；
- 锁     → 内存锁（单进程有效）。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.db.session import redis_client

logger = logging.getLogger(__name__)

# ===== key 前缀 =====
_PREFIX = "oj"
_BLACKLIST = f"{_PREFIX}:bl:jwt"        # 黑名单
_RATE_LIMIT = f"{_PREFIX}:rl"           # 限流
_LOCK = f"{_PREFIX}:lock:vis"           # 迁移锁


# ============================================================================
# 底层：带降级的 Redis 调用
# ============================================================================


async def _safe_redis(coro, fallback, op: str):
    """执行 Redis 协程；失败时记录一次并返回 fallback。

    不抛异常、不重试 —— 保证 Redis 故障不影响业务主流程。
    """
    try:
        return await coro
    except Exception as exc:  # 连接拒绝 / 超时 / 任何 Redis 异常
        logger.warning("[redis] %s 失败，降级处理: %s", op, exc)
        return fallback


async def redis_alive() -> bool:
    """Redis 是否可用（供健康检查与调试用）。"""
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False


# ============================================================================
# JWT 黑名单：登出 / 改密后让旧 token 立即失效
# ============================================================================
# Redis 不可用时的内存兜底：{jti: 过期时间戳}
_mem_blacklist: dict[str, float] = {}


async def blacklist_jwt(jti: str, ttl_seconds: int) -> bool:
    """把 jti 加入黑名单，ttl 为剩余有效秒数（过期后自动清理）。

    Returns:
        True 表示已写入（Redis 或内存兜底）。
    """
    if not jti or ttl_seconds <= 0:
        return False

    async def _redis() -> bool:
        await redis_client.setex(f"{_BLACKLIST}:{jti}", ttl_seconds, "1")
        return True

    ok = await _safe_redis(_redis(), False, f"blacklist set {jti[:8]}")
    if ok:
        return True

    # 降级：写入内存（单进程有效）
    _mem_blacklist[jti] = time.time() + ttl_seconds
    return True


async def is_jwt_blacklisted(jti: str) -> bool:
    """jti 是否已被拉黑。Redis 不可用时查内存兜底。"""
    if not jti:
        return False

    async def _redis() -> bool:
        return bool(await redis_client.exists(f"{_BLACKLIST}:{jti}"))

    res = await _safe_redis(_redis(), None, f"blacklist get {jti[:8]}")
    if res is not None:
        return bool(res)

    # 降级：查内存
    exp = _mem_blacklist.get(jti)
    if exp is None:
        return False
    if exp <= time.time():
        _mem_blacklist.pop(jti, None)
        return False
    return True


# ============================================================================
# 接口限流：固定窗口（按分钟），用于登录 / 注册等敏感接口
# ============================================================================
# Redis 不可用时的内存兜底：{窗口key: count}
_mem_ratelimit: dict[str, int] = {}


async def rate_limit_hit(bucket: str, limit: int, window_seconds: int = 60) -> bool:
    """在 bucket 上计一次数，返回是否「超限」（True = 应拒绝）。

    Args:
        bucket: 限流维度标识，如 `login:127.0.0.1`
        limit:  窗口内允许的最大次数
        window_seconds: 窗口长度（默认 60s）

    Redis 可用时用 INCR + EXPIRE（原子、多进程共享）；
    不可用时退回内存计数（单进程有效）。
    """
    window_id = int(time.time()) // window_seconds
    key = f"{_RATE_LIMIT}:{bucket}:{window_id}"

    async def _redis() -> bool:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds + 5)
        count: int = (await pipe.execute())[0]
        # count 为 None 时表示管道异常，按放行处理
        return bool(count) and int(count) > limit

    res = await _safe_redis(_redis(), None, f"ratelimit {bucket}")
    if res is not None:
        return bool(res)

    # 降级：内存计数
    _mem_ratelimit[key] = _mem_ratelimit.get(key, 0) + 1
    # 顺手清理旧窗口，避免 dict 无限增长
    if len(_mem_ratelimit) > 1000:
        stale = [k for k in _mem_ratelimit if not k.endswith(str(window_id))]
        for k in stale:
            _mem_ratelimit.pop(k, None)
    return _mem_ratelimit[key] > limit


# ============================================================================
# 访客迁移互斥锁：防并发登录时重复认领匿名报告
# ============================================================================
_mem_locks: dict[str, float] = {}


async def acquire_visitor_lock(visitor_id: str, ttl_seconds: int = 30) -> bool:
    """尝试获取访客迁移锁，成功返回 True（调用方负责后续释放）。

    Redis 用 SET NX EX 原子抢占；不可用时用内存锁兜底。
    """
    if not visitor_id:
        return False
    key = f"{_LOCK}:{visitor_id}"

    async def _redis() -> bool:
        return bool(await redis_client.set(key, "1", nx=True, ex=ttl_seconds))

    res = await _safe_redis(_redis(), None, f"lock {visitor_id[:8]}")
    if res is not None:
        return bool(res)

    # 降级：内存锁
    now = time.time()
    exp = _mem_locks.get(visitor_id)
    if exp and exp > now:
        return False
    _mem_locks[visitor_id] = now + ttl_seconds
    return True


async def release_visitor_lock(visitor_id: str) -> None:
    """释放访客迁移锁（失败静默，锁会自然过期）。"""
    if not visitor_id:
        return
    key = f"{_LOCK}:{visitor_id}"

    async def _redis() -> bool:
        await redis_client.delete(key)
        return True

    await _safe_redis(_redis(), False, f"unlock {visitor_id[:8]}")
    _mem_locks.pop(visitor_id, None)


# ============================================================================
# 运维：查看当前 oj:* 键空间（调试用）
# ============================================================================


async def dump_keys(pattern: str = "oj:*", limit: int = 100) -> list[str]:
    """列出匹配 pattern 的 key（最多 limit 个），Redis 不可用返回空列表。

    仅用于调试 / 健康检查，生产环境慎用 SCAN 全量遍历。
    """
    async def _redis() -> list[str]:
        keys: list[str] = []
        async for k in redis_client.scan_iter(match=pattern, count=200):
            keys.append(k)
            if len(keys) >= limit:
                break
        return keys

    res = await _safe_redis(_redis(), None, "scan keys")
    return res if isinstance(res, list) else []
