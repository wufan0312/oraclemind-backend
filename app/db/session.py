"""异步数据库会话与探活工具。

- engine：SQLAlchemy 2.0 async engine（asyncpg 驱动，pool_pre_ping 自动剔除失效连接）
- async_session：异步会话工厂
- get_db：FastAPI 依赖，请求级会话（请求结束自动提交/回滚）
- check_database / check_redis：健康检查用探活
"""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ===== 数据库引擎 =====
# R5 修复：SQL echo（会打印含绑定参数的 SQL）仅在 debug 开启**且非生产**时启用。
# 即便误在生产环境把 debug 置 True，也绝不会把带绑定参数的 SQL 打到 stdout（防泄露）。
_echo = settings.debug and not settings.is_production

# SQLite 不支持 pool_size / max_overflow / pool_pre_ping，需分支处理
if settings.is_sqlite:
    engine = create_async_engine(
        settings.database_url,
        echo=_echo,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=_echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ===== Redis 客户端 =====
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def _autocommit_pending(session: AsyncSession) -> None:
    """R6 防御：处理器正常结束且未显式提交时，若有未决变更则自动提交，避免静默数据丢失。

    - 已显式 ``commit`` 的会话 pending 集合为空，不会重复提交；
    - 异常路径（已 rollback）不进入本函数。
    """
    if session.new or session.dirty or session.deleted:
        await session.commit()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            # R6：未显式提交但有变更时自动提交（防静默丢失；已提交则 pending 为空，无副作用）
            await _autocommit_pending(session)


# ===== 探活 =====
async def check_database() -> bool:
    """执行 SELECT 1 探活 PostgreSQL；失败返回 False 而非抛出。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - 连接失败路径
        logger.warning("数据库探活失败: %s", exc)
        return False


async def check_redis() -> bool:
    """PING 探活 Redis；失败返回 False 而非抛出。"""
    try:
        await redis_client.ping()
        return True
    except Exception as exc:  # pragma: no cover - 连接失败路径
        logger.warning("Redis 探活失败: %s", exc)
        return False


async def close_connections() -> None:
    """关闭引擎与 Redis 连接（应用退出时调用）。"""
    await engine.dispose()
    await redis_client.aclose()
