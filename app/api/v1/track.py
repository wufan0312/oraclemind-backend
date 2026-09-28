"""漏斗埋点上报 —— P0 占卜 → 心理付费转化追踪（匿名，前端调用）。

- POST /api/v1/track：上报单个 funnel 事件（visitor_id 必填，防垃圾写入）；
- 不做业务鉴权（匿名漏斗数据无敏感信息），但要求 visitor_id 与基础字段合规；
- admin 后端经共享库直接聚合读取，不在主站暴露查询接口。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.track_event import TrackEvent

router = APIRouter(prefix="/track", tags=["track"])


class TrackEventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64, description="事件类型")
    source: str = Field(..., min_length=1, max_length=32, description="入口来源：bugua / tarot")
    visitor_id: str = Field(..., min_length=1, max_length=64, description="访客ID（匿名归因）")
    props: dict | None = Field(default=None, description="附加属性，如 mood / score")


class TrackEventOut(BaseModel):
    id: int
    event_type: str
    source: str
    visitor_id: str
    created_at: str


@router.post("", status_code=201, response_model=TrackEventOut)
async def create_track_event(
    payload: TrackEventCreate,
    db: AsyncSession = Depends(get_db),
) -> TrackEventOut:
    """上报一个漏斗事件。匿名可用，visitor_id 必填。"""
    obj = TrackEvent(
        event_type=payload.event_type,
        source=payload.source,
        visitor_id=payload.visitor_id,
        props=payload.props,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return TrackEventOut(
        id=obj.id,
        event_type=obj.event_type,
        source=obj.source,
        visitor_id=obj.visitor_id,
        created_at=obj.created_at.isoformat() if obj.created_at else "",
    )
