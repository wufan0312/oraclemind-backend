"""审批 Gate 核心服务（P1 Harness 化）。

责任边界：
- ``ApprovalService`` 只做 CRUD + 状态机，不依赖任何 request / auth 上下文，便于单测；
  调用方（路由层）负责把 user / visitor 解析成 actor_type / actor_id 再传入。
- ``verify_approval``：业务接口在真正执行副作用前调用，校验「存在 + 已批准 + 未消费
  + 动作类型匹配 + 归属匹配」，否则抛 428（Precondition Required）。调用方随后自行
  ``consume``。
- ``ActionType`` 仅作常量参考，落库为字符串。

与 P0 Boundary / Observability 的关系：
- Boundary 校验「模型产出」；ApprovalGate 校验「人类是否已对本次高风险操作点头」；
- trace_id 关联 P0-2 的决策树，审批记录可被审计链路追踪。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval


class ActionType(str, Enum):
    """高风险动作类型（落库为字符串）。"""

    DONATION = "donation"
    PREMIUM = "premium"
    COMMUNITY_POST = "community_post"
    SHARE = "share"
    DELETE = "delete"
    CUSTOM = "custom"


# 允许的动作类型白名单（防任意字符串注入）
_ALLOWED_ACTIONS = {a.value for a in ActionType}


class ApprovalService:
    """审批记录 CRUD + 状态机。"""

    async def request(
        self,
        db: AsyncSession,
        *,
        action_type: str,
        actor_type: str,
        actor_id: str | None,
        summary: str = "",
        payload: dict | None = None,
        trace_id: str | None = None,
    ) -> Approval:
        """创建一条 pending 审批。"""
        if action_type not in _ALLOWED_ACTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知审批动作类型：{action_type}",
            )
        if actor_type not in ("user", "visitor"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知操作者类型：{actor_type}",
            )
        appr = Approval(
            action_type=action_type,
            actor_type=actor_type,
            actor_id=actor_id,
            summary=(summary or "")[:256],
            payload=payload,
            trace_id=trace_id,
            status="pending",
            consumed=False,
        )
        db.add(appr)
        await db.flush()
        return appr

    async def approve(
        self,
        db: AsyncSession,
        approval_id: int,
        *,
        actor_type: str,
        actor_id: str | None,
        note: str | None = None,
    ) -> Approval:
        """审批通过（仅允许发起人操作）。"""
        appr = await self._load_and_check_owner(db, approval_id, actor_type, actor_id)
        if appr.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"审批已处于 {appr.status} 状态，无法重复审批",
            )
        appr.status = "approved"
        appr.decision_note = (note or "")[:256] or None
        appr.decided_at = datetime.now(timezone.utc)
        return appr

    async def reject(
        self,
        db: AsyncSession,
        approval_id: int,
        *,
        actor_type: str,
        actor_id: str | None,
        note: str | None = None,
    ) -> Approval:
        """审批拒绝（仅允许发起人操作）。"""
        appr = await self._load_and_check_owner(db, approval_id, actor_type, actor_id)
        if appr.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"审批已处于 {appr.status} 状态，无法重复审批",
            )
        appr.status = "rejected"
        appr.decision_note = (note or "")[:256] or None
        appr.decided_at = datetime.now(timezone.utc)
        return appr

    async def get(self, db: AsyncSession, approval_id: int) -> Approval | None:
        from sqlalchemy import select

        return (
            await db.execute(select(Approval).where(Approval.id == approval_id))
        ).scalar_one_or_none()

    async def list_for(
        self, db: AsyncSession, actor_type: str, actor_id: str | None, limit: int = 20
    ) -> list[Approval]:
        from sqlalchemy import select

        stmt = select(Approval).where(Approval.actor_type == actor_type)
        if actor_id is not None:
            stmt = stmt.where(Approval.actor_id == actor_id)
        else:
            stmt = stmt.where(Approval.actor_id.is_(None))
        stmt = stmt.order_by(Approval.created_at.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    async def consume(self, db: AsyncSession, approval_id: int) -> None:
        """标记已消费（防重放）。"""
        appr = await self.get(db, approval_id)
        if appr is not None:
            appr.consumed = True

    # ---- 内部工具 ----

    async def _load_and_check_owner(
        self, db: AsyncSession, approval_id: int, actor_type: str, actor_id: str | None
    ) -> Approval:
        appr = await self.get(db, approval_id)
        if appr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="审批记录不存在"
            )
        # 横向越权防护：仅允许发起人审批自己的请求
        if appr.actor_type != actor_type or appr.actor_id != actor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权操作他人的审批请求"
            )
        return appr


async def verify_approval(
    db: AsyncSession,
    approval_id: int | None,
    *,
    expected_action_type: str,
    actor_type: str,
    actor_id: str | None,
) -> Approval:
    """业务接口执行副作用前调用：校验审批已通过且未重放。

    通过则返回 Approval（调用方随后应 ``ApprovalService.consume``）；
    否则抛 428（Precondition Required）。
    """
    if approval_id is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="该操作需要人工审批（approval_id 缺失）",
        )
    svc = ApprovalService()
    appr = await svc.get(db, approval_id)
    if appr is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="审批记录不存在或已失效",
        )
    if appr.action_type != expected_action_type:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=f"审批动作类型不匹配（期望 {expected_action_type}，实际 {appr.action_type}）",
        )
    if appr.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=f"操作未通过人工审批（当前状态：{appr.status}）",
        )
    if appr.consumed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该审批已被使用，不能重复执行（防重放）",
        )
    # 归属校验：业务执行者须与审批发起人一致
    if appr.actor_type != actor_type or appr.actor_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="审批发起人与执行人不一致",
        )
    return appr
