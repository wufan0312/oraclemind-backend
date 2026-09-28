"""量表 API —— 右轨心理学产品的结构化测评入口（v1）。

端点：
- GET  /scales                  量表列表
- GET  /scales/{slug}           量表详情（题目 + 选项，供前端渲染答题）
- POST /scales/{slug}/score     提交作答 → 维度分 + 自我觉察摘要（并落库留存）

合规定位：量表为自我觉察 / 成长导向，非诊断、非病理；题目与计分以服务端为准。
本增量完成作答持久化（ScaleAttempt），为后续 AI 心理报告 / 付费闸门 / 个人中心留存提供真源。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_optional_user, get_visitor_id
from app.core.audit import audited_commit
from app.core.ownership import actor_id_of
from app.db.session import get_db
from app.models.scale_attempt import ScaleAttempt
from app.models.user import User
from app.schemas.scale import (
    DimensionScore,
    ScaleDetail,
    ScaleDimension,
    ScaleListItem,
    ScaleQuestion,
    ScaleScoreResult,
    ScaleScoreSubmit,
)
from app.services import scale_catalog
from app.services.scale_engine import score_scale

router = APIRouter(tags=["心理学量表"])


@router.get("/scales", response_model=list[ScaleListItem], summary="量表列表")
async def list_scales() -> list[ScaleListItem]:
    """返回已注册量表卡片（不含题目，前端按需拉详情）。"""
    return [
        ScaleListItem(
            slug=s["slug"],
            title=s["title"],
            tagline=s.get("tagline", ""),
            description=s.get("description", ""),
            estimatedMinutes=s.get("estimatedMinutes", 0),
            questionCount=len(s.get("items", [])),
        )
        for s in scale_catalog.SCALES.values()
    ]


@router.get("/scales/{slug}", response_model=ScaleDetail, summary="量表详情")
async def get_scale(slug: str) -> ScaleDetail:
    """返回量表题目与选项（供前端渲染答题页）。"""
    s = scale_catalog.get_scale(slug)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"量表不存在：{slug}")
    return ScaleDetail(
        slug=s["slug"],
        title=s["title"],
        tagline=s.get("tagline", ""),
        description=s.get("description", ""),
        disclaimer=s.get("disclaimer", ""),
        estimatedMinutes=s.get("estimatedMinutes", 0),
        options=s.get("options", []),
        dimensions=[ScaleDimension(key=d["key"], name=d["name"]) for d in s.get("dimensions", [])],
        questions=[
            ScaleQuestion(id=it["id"], text=it["text"], dimension=it["dimension"], options=s.get("options", []))
            for it in s.get("items", [])
        ],
    )


@router.post("/scales/{slug}/score", response_model=ScaleScoreResult, summary="提交作答并计分")
async def submit_score(
    slug: str,
    payload: ScaleScoreSubmit,
    user: User | None = Depends(get_optional_user),
    visitor_id: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> ScaleScoreResult:
    """对一份作答计分，返回各维度 0–100 分、等级与自我觉察摘要，并落库留存。

    安全：题目与计分别来自服务端，客户端只传作答值，无法篡改题干或计分；
    作答（answers）与计分（score_json）落 scale_attempts，归属按 user / visitor 双轨。
    """
    s = scale_catalog.get_scale(slug)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"量表不存在：{slug}")
    try:
        result = score_scale(s, payload.answers)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # 作答持久化：归属优先 user，其次 visitor，皆空则 anonymous；失败不阻断计分返回
    attempt_id = ""
    try:
        owner_type = "user" if user is not None else ("visitor" if visitor_id else "anonymous")
        attempt = ScaleAttempt(
            slug=slug,
            user_id=user.id if user is not None else None,
            visitor_id=visitor_id or "",
            owner_type=owner_type,
            answers_json={k: int(v) for k, v in payload.answers.items()},
            score_json=result["dimensions"],
            summary=result["summary"],
        )
        db.add(attempt)
        await db.flush()
        await audited_commit(
            db,
            "submit_scale_score",
            actor_type=owner_type,
            actor_id=actor_id_of(user, visitor_id),
            target=f"{slug}:{attempt.id}",
        )
        await db.refresh(attempt)
        attempt_id = str(attempt.id)
    except Exception as exc:  # 留存失败仅告警，不影响计分结果返回（量表核心功能可用）
        import logging

        logging.getLogger(__name__).warning("量表作答落库失败（已忽略）：%s", exc)

    return ScaleScoreResult(
        slug=result["slug"],
        dimensions=[DimensionScore(**d) for d in result["dimensions"]],
        summary=result["summary"],
        disclaimer=result["disclaimer"],
        attemptId=attempt_id,
    )
