"""漏斗埋点事件 —— P0 占卜流量 → 心理付费转化追踪。

设计要点：
- track_events 由主站 Alembic 建表（业务行为数据归主站），admin 后端只读共享；
- 匿名上报，visitor_id 必填（前端恒有），用于跨设备去重与漏斗归因；
- event_type 取值：bridge_exposure / bridge_mood_submit / bridge_assessment_click / assessment_paid；
- source 取值：bugua / tarot（assessment_paid 时复用入口来源做归因）。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrackEvent(Base):
    """漏斗埋点事件。"""

    __tablename__ = "track_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="事件类型"
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="入口来源：bugua / tarot"
    )
    visitor_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="访客ID（匿名归因）"
    )
    props: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="附加属性，如 mood / score"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, comment="事件时间"
    )
