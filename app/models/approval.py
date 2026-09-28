"""审批 Gate 记录 —— Human-in-the-loop 人工确认留痕（P1 Harness 化改造）。

设计目标：高风险操作（付费 / 外发 / 删除）在执行「真正副作用」之前，必须创建一条
pending 审批；经用户确认（approve）后，业务接口凭 ``approval_id`` 才能放行，
且用完即标记 ``consumed=True`` 防重放。

状态机：
    pending --approve--> approved --consume--> (业务执行) / 直接 consumed
    pending --reject--> rejected
    pending --(过期)--> expired  （由业务惰性标记，本模型不自动过期）

归属性：以 actor_type + actor_id 标记发起人，approve/reject 仅允许同身份操作，
避免越权审批他人请求（横向越权防护）。
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Approval(Base):
    """审批 Gate 记录表。"""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # 动作类型：donation / premium / community_post / share / delete / custom
    action_type: Mapped[str] = mapped_column(
        String(32), index=True, comment="动作类型"
    )
    # 操作者类型：user / visitor
    actor_type: Mapped[str] = mapped_column(
        String(16), default="visitor", server_default="visitor", comment="操作者类型"
    )
    # 操作者ID：登录用户ID 或 访客ID
    actor_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="操作者标识（用户ID或访客ID）"
    )
    # 展示给用户确认的摘要
    summary: Mapped[str] = mapped_column(
        String(256), default="", server_default="", comment="展示给用户的确认摘要"
    )
    # 业务上下文快照（按需脱敏，不存敏感原文）
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="业务上下文快照（脱敏）"
    )
    # 状态：pending / approved / rejected / expired
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        index=True,
        comment="pending/approved/rejected/expired",
    )
    # 是否已被执行消费（防重放）
    consumed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", comment="是否已被业务消费（防重放）"
    )
    # 关联 Observability trace（P0-2 决策树追踪）
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="关联 Observability trace"
    )
    # 审批备注（拒绝原因等）
    decision_note: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="审批备注"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审批时间"
    )
