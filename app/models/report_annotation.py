"""报告批注模型 —— 用户写在报告某一段结论旁的个人笔记。

设计取舍：
- 批注挂在 report_id 上，用 anchor 定位到报告内的具体区块（如 summary / cards.1 /
  timeline.2 / dims.事业），anchor 为空表示整篇批注；
- 归属沿用 Report 的统一 Owner 模型（owner_type + user_id / visitor_id），
  避免新增一套身份体系；
- 删除报告时批注不级联物理删除（报告是软删），由查询侧按 report_id 过滤。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportAnnotation(Base):
    """报告批注：用户对报告中某一段结论的个人笔记。"""

    __tablename__ = "report_annotations"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        index=True,
        comment="所属报告ID（reports.id，软删报告保留历史批注）",
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True, comment="登录用户ID"
    )
    visitor_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="访客ID（匿名批注归属）"
    )
    owner_type: Mapped[str] = mapped_column(
        String(8), default="visitor", server_default="visitor", comment="归属：visitor / user"
    )
    anchor: Mapped[str] = mapped_column(
        String(64), default="", comment="锚点：报告内区块标识（summary / cards.1 / dims.事业 / timeline.0），空=整篇"
    )
    anchor_label: Mapped[str] = mapped_column(
        String(128), default="", comment="锚点展示名（如「综合结论」「关键提醒 · 关键决策期」）"
    )
    quote: Mapped[str] = mapped_column(
        String(512), default="", comment="被批注的原文片段（≤200字，便于回看时对照）"
    )
    content: Mapped[str] = mapped_column(Text, default="", comment="批注正文")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def reportId(self) -> int:
        """camelCase 别名：供 Pydantic from_attributes 序列化使用。"""
        return self.report_id

    @property
    def anchorLabel(self) -> str:
        """camelCase 别名：锚点展示名。"""
        return self.anchor_label
