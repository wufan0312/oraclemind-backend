"""数据库迁移入口 —— 应用启动时自动执行（幂等、可追踪、可回滚）。

落地缺陷报告 P1 改进建议「引入 Alembic 迁移工具」：用 Alembic 取代原先
``create_all`` + 手写 ``ALTER`` 的幂等迁移方案，实现可追踪、可回滚的 schema 管理。

- ``alembic upgrade head`` 把数据库对齐到最新 schema；
- 数据库已是最新时 upgrade 为 no-op，安全幂等；
- 迁移历史由 ``alembic_version`` 表追踪，支持 ``alembic downgrade`` 回滚。

容错：若数据库暂不可达（如依赖未启动），仅记录告警并继续，不阻断应用启动。
健康检查端点会如实反映数据库状态。
"""

import asyncio
import logging
from pathlib import Path

import alembic
from alembic.config import Config
from alembic import command

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _enable_sqlite_wal() -> None:
    """SQLite 开启 WAL 日志模式（写不阻塞读、并发写不再全库锁）。

    仅对 SQLite 生效；WAL 模式持久化在数据库文件头，启动时设置一次即长期
    生效，重启后自动保持。``synchronous=NORMAL`` 是 WAL 的标准配套，在 WAL
    下仍保证崩溃安全、且写入更快。PostgreSQL 分支不调用本函数。

    用 aiosqlite 直连 DB 文件执行 PRAGMA：WAL 是文件级持久设置，直连设置即
    永久生效，且绕开 SQLAlchemy 连接池的事务/隔离级别差异，跨版本稳健。
    """
    if not settings.is_sqlite:
        return
    import aiosqlite

    from app.db.session import engine  # 延迟导入，避免循环依赖

    path = engine.url.database
    if not path or path == ":memory:":
        return
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        async with db.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
        mode = row[0] if row else None
    logger.info("SQLite 已切换为 WAL 日志模式（当前: %s）", mode)


# 项目根目录（oraclemind-backend）：app/db/init_db.py -> parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"
_MIGRATIONS_DIR = _BACKEND_ROOT / "migrations"


def _build_alembic_config() -> Config:
    """构造 Alembic 配置：脚本目录指向 migrations，URL 由 env.py 从 settings 注入。"""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    return cfg


def run_migrations() -> None:
    """同步执行 alembic upgrade head（迁移工具核心）。"""
    command.upgrade(_build_alembic_config(), "head")


async def init_db() -> None:
    """Alembic 迁移：把数据库对齐到最新 schema（幂等）。

    容错：数据库不可达时仅告警，健康检查如实反映数据库状态。
    """
    # 生产/Vercel 误用 SQLite 直接失败（在 try 之外，避免被容错吞掉）
    settings.validate_for_runtime()
    try:
        await asyncio.to_thread(run_migrations)
        logger.info("数据库迁移完成（alembic upgrade head，幂等）")
    except Exception as exc:  # pragma: no cover - 依赖缺失路径
        logger.warning(
            "数据库迁移跳过：%s。服务以降级模式运行，"
            "健康检查将标记数据库为 down。",
            exc,
        )

    # SQLite 开启 WAL：写并发优化（独立于迁移，失败仅告警不阻断启动）
    try:
        await _enable_sqlite_wal()
    except Exception as exc:  # pragma: no cover
        logger.warning("SQLite WAL 配置跳过：%s", exc)


if __name__ == "__main__":
    run_migrations()
    print("migrations applied")
