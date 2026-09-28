"""审批 Gate Pydantic 模型（P1 Harness 化）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApprovalCreate(BaseModel):
    """创建审批请求（前端在执行高风险操作前调用）。"""

    actionType: str = Field(..., max_length=32, description="动作类型：donation/premium/community_post/share/delete/custom")
    summary: str = Field(default="", max_length=256, description="展示给用户确认的摘要")
    payload: dict | None = Field(default=None, description="业务上下文快照（脱敏）")
    traceId: str | None = Field(default=None, max_length=64, description="关联 Observability trace")


class ApprovalDecision(BaseModel):
    """审批决策（确认 / 拒绝）。"""

    note: str | None = Field(default=None, max_length=256, description="审批备注（拒绝原因等）")


class ApprovalOut(BaseModel):
    """审批记录详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actionType: str
    actorType: str
    actorId: str | None = None
    summary: str = ""
    status: str
    consumed: bool
    traceId: str | None = None
    decisionNote: str | None = None
    createdAt: datetime
    decidedAt: datetime | None = None
