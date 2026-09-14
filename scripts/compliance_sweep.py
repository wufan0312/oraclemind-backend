"""合规扫描脚本 —— PII 过期 / 软删超时匿名数据（§4.6 安全与合规）。

独立运行：
    cd oraclemind-backend
    python -m scripts.compliance_sweep

行为（全部为软删 / 日志，物理删除仅 GDPR 显式请求）：
  1. 幂等确保 reports / users 存在 deleted_at 列；
  2. 软删 30 天以上无活动的匿名报告（owner_type='visitor'，合规：PII 30 天过期）；
  3. 登录用户 90 天无登录 → 打印提醒（邮件系统接入前仅日志，标注 TODO）。
不读取、不修改用户真实内容，仅按时间戳做软删/标记，符合「软删为主」原则。
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect as sa_inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 —— 注册全部 ORM 模型，供 create_all
from app.core.audit import AuditLog
from app.core.config import settings
from app.db.base import Base
from app.models.report import Report
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compliance_sweep")


async def _ensure_deleted_at(engine) -> None:
    async with engine.begin() as conn:
        for table in ("reports", "users"):

            def _cols(sync_conn) -> set[str]:
                return {c["name"] for c in sa_inspect(sync_conn).get_columns(table)}

            cols = await conn.run_sync(_cols)
            if "deleted_at" not in cols:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP"))
                logger.info("%s.deleted_at 已补充", table)


async def run() -> dict:
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.is_sqlite else {},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_deleted_at(engine)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    anon_cutoff = now - timedelta(days=30)
    user_cutoff = now - timedelta(days=90)
    stats = {"anon_soft_deleted": 0, "stale_users": 0}

    async with Session() as db:
        # 1. 软删 30 天以上匿名报告
        res = await db.execute(
            select(Report).where(
                Report.owner_type == "visitor",
                Report.deleted_at.is_(None),
                Report.created_at < anon_cutoff,
            )
        )
        victims = res.scalars().all()
        for r in victims:
            r.deleted_at = now
        if victims:
            await db.commit()
            stats["anon_soft_deleted"] = len(victims)
            logger.info("软删 %d 条超时匿名报告", len(victims))

        # 2. 90 天无登录用户 → 提醒（邮件接入前仅日志）
        res = await db.execute(
            select(User).where(User.deleted_at.is_(None), User.updated_at < user_cutoff)
        )
        stale = res.scalars().all()
        stats["stale_users"] = len(stale)
        for u in stale:
            # TODO: 接入邮件系统后改为实际发送 PII 提醒邮件
            logger.warning(
                "用户 %s(%d) 已 %d 天未登录，需发送 PII 提醒邮件（当前仅日志）",
                u.username,
                u.id,
                90,
            )
            try:
                db.add(
                    AuditLog(
                        action="pii_reminder_due",
                        actor_type="user",
                        actor_id=str(u.id),
                        detail={"idle_days": 90},
                    )
                )
            except Exception:
                pass
        if stale:
            await db.commit()

    await engine.dispose()
    logger.info("合规扫描完成：%s", stats)
    return stats


if __name__ == "__main__":
    out = asyncio.run(run())
    print(out)
