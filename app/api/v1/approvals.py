"""审批 Gate API（P1 Harness 化 · Human-in-the-loop）。

流程：
1. 前端要执行高风险操作 → POST /approvals 创建 pending 审批（拿到 id + summary）；
2. 前端弹确认框展示 summary → 用户点确认 → POST /approvals/{id}/approve；
3. 前端再调业务接口并带 approvalId → 业务接口用 verify_approval 校验放行；
4. 业务成功后标记 consumed 防重放。

身份：创建/审批均按「登录用户 or 访客」隔离，跨身份审批被 403 拒绝（横向越权防护）。
"""

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_optional_user, get_visitor_id
from app.core.approval import ApprovalService, verify_approval
from app.core.ownership import actor_id_of
from app.db.session import get_db
from app.models.user import User
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalOut

router = APIRouter(tags=["审批 Gate"])


def _actor(user: User | None, visitor_id: str | None) -> tuple[str, str | None]:
    actor_type = "user" if user is not None else "visitor"
    return actor_type, actor_id_of(user, visitor_id)


@router.post(
    "/approvals",
    response_model=ApprovalOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建审批请求（高风险操作前）",
)
async def create_approval(
    payload: ApprovalCreate,
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    actor_type, actor_id = _actor(user, visitor_id)
    svc = ApprovalService()
    appr = await svc.request(
        db,
        action_type=payload.actionType,
        actor_type=actor_type,
        actor_id=actor_id,
        summary=payload.summary,
        payload=payload.payload,
        trace_id=payload.traceId,
    )
    await db.commit()
    await db.refresh(appr)
    return ApprovalOut.model_validate(appr)


@router.get("/approvals", response_model=list[ApprovalOut], summary="我的审批列表")
async def list_approvals(
    limit: int = Query(default=20, ge=1, le=100),
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalOut]:
    actor_type, actor_id = _actor(user, visitor_id)
    svc = ApprovalService()
    rows = await svc.list_for(db, actor_type, actor_id, limit=limit)
    return [ApprovalOut.model_validate(r) for r in rows]


@router.get(
    "/approvals/{approval_id}",
    response_model=ApprovalOut,
    summary="审批详情",
)
async def get_approval(
    approval_id: int,
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    actor_type, actor_id = _actor(user, visitor_id)
    svc = ApprovalService()
    appr = await svc.get(db, approval_id)
    if appr is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "审批不存在"})
    # 仅允许发起人查看详情（防越权窥探）
    if appr.actor_type != actor_type or appr.actor_id != actor_id:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "无权查看该审批"})
    return ApprovalOut.model_validate(appr)


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalOut,
    summary="审批通过（人工确认）",
)
async def approve_approval(
    approval_id: int,
    payload: ApprovalDecision,
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    actor_type, actor_id = _actor(user, visitor_id)
    svc = ApprovalService()
    appr = await svc.approve(
        db, approval_id, actor_type=actor_type, actor_id=actor_id, note=payload.note
    )
    await db.commit()
    await db.refresh(appr)
    return ApprovalOut.model_validate(appr)


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalOut,
    summary="审批拒绝",
)
async def reject_approval(
    approval_id: int,
    payload: ApprovalDecision,
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    actor_type, actor_id = _actor(user, visitor_id)
    svc = ApprovalService()
    appr = await svc.reject(
        db, approval_id, actor_type=actor_type, actor_id=actor_id, note=payload.note
    )
    await db.commit()
    await db.refresh(appr)
    return ApprovalOut.model_validate(appr)
