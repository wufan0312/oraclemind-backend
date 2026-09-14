"""排盘报告模型 —— 一次排盘会话的完整快照。

对应 tech_stack_plan §5 排盘域 comprehensive_reports 表。
一次排盘 = 出生信息（params）+ 各术数结果快照（results，key 为术数名）。
summary 预留 AI 综合运势摘要。
visitor_id 实现匿名云存储：按访客ID隔离数据，无需用户认证。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    """综合排盘报告：输入参数 + 各术数结果 JSON 快照。

    统一 Owner 模型（数据存储重设计方案 §三）：
    - 未登录（匿名）：visitor_id 有值，user_id 为 NULL，owner_type='visitor'
    - 已登录：user_id 有值（绑定账号），owner_type='user'；visitor_id 保留作溯源
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="登录用户ID（为空则为匿名访客）",
    )
    visitor_id: Mapped[str] = mapped_column(String(64), index=True, comment="访客ID（匿名云存储标识 / 登录后保留作溯源）")
    owner_type: Mapped[str] = mapped_column(
        String(8),
        default="visitor",
        server_default="visitor",
        comment="数据归属：visitor=匿名 / user=登录用户",
    )
    title: Mapped[str] = mapped_column(String(64), default="命理综合报告")
    params: Mapped[dict] = mapped_column(JSON, default=dict, comment="排盘输入参数（出生信息/时辰/性别/问题）")
    results: Mapped[dict] = mapped_column(JSON, default=dict, comment="各术数排盘结果快照 {bazi, ziwei, liuyao, ...}")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="综合运势摘要（预留 AI 生成）")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # --- 报告管理增强（收藏/置顶 + 版本管理）---
    favorited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="是否收藏（收藏项在列表中可单独筛选，并默认排在前面）",
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="是否置顶（置顶项永远排在最前，优先于收藏）",
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父报告ID：「换个说法」产生的版本链，根版本为 NULL",
    )
    variant: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="版本号：根版本 0，「换个说法」第 N 次为 N",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="软删时间戳（合规：删除走软删，物理删除仅 GDPR 显式请求）",
    )

    @property
    def visitorId(self) -> str:
        """camelCase 别名：供 Pydantic from_attributes 序列化使用（与前端字段一致）。"""
        return self.visitor_id

    @property
    def parentId(self) -> int | None:
        """camelCase 别名：版本链父报告ID。"""
        return self.parent_id
