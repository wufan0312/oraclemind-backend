"""审计埋点助手 —— 在关键写操作路由中调用，失败不影响主流程。

满足 §4.6 合规三件套之二：所有写操作（登录/排盘/分享）记 audit_log 表。
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    db: AsyncSession,
    action: str,
    actor_type: str = "user",
    actor_id: str | None = None,
    target: str | None = None,
    detail: dict | None = None,
) -> None:
    """把审计日志加入当前 session；由调用方统一 commit（缺陷报告 P1-5）。

    **不再自行 commit / rollback**：审计行与业务行处在同一事务，调用方一次
    ``await db.commit()`` 二者一起落库或一起回滚，杜绝「业务成功但审计丢失」
    或「审计提交但业务回滚」的不一致。

    仅 ``db.add`` 几乎不会抛异常；即便抛了也只记日志，绝不回滚业务事务。

    actor_id 统一转 str（None 表示系统/匿名）。
    """
    try:
        db.add(
            AuditLog(
                action=action,
                actor_type=actor_type,
                actor_id=str(actor_id) if actor_id is not None else None,
                target=target,
                detail=detail,
            )
        )
    except Exception:  # pragma: no cover - 审计失败不应影响业务
        logger.warning("审计记录失败（不影响主流程）", exc_info=True)


async def audited_commit(
    db: AsyncSession,
    action: str,
    actor_type: str = "user",
    actor_id: str | None = None,
    target: str | None = None,
    detail: dict | None = None,
) -> None:
    """记录审计并与业务数据同事务提交（Q4：消除 ``record_audit(...); await db.commit()`` 样板）。

    等价于先 ``record_audit(db, ...)`` 再 ``await db.commit()``：审计行与业务行处于同一事务，
    一次 commit 一起落库或一起回滚，杜绝「业务成功但审计丢失」或「审计提交但业务回滚」。

    调用前请确保业务行已 ``db.add``（通常先 ``db.flush()`` 拿 ID 供审计引用 target）。
    """
    await record_audit(
        db, action, actor_type=actor_type, actor_id=actor_id, target=target, detail=detail
    )
    await db.commit()
