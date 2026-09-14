"""用户分享记录模型 —— 各模块的保存/分享内容（登录态隔离）。

与 reports 同一数据库，但按 用户ID + 模块 唯一：
- 首次生成分享内容直接落库；用户再次进入页面时从库读取，不再重新生成（省 CogView 配额）。
- 重新生成会覆盖同一 (user_id, module) 的记录。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Share(Base):
    """用户在某模块下的分享内容快照（文案 + 配图）。"""

    __tablename__ = "shares"

    # 缺陷报告 P1-6：由数据库层保证 (user_id, module) 唯一，
    # 取代原先纯应用层的 select-then-upsert，消除并发下重复记录/丢失更新。
    __table_args__ = (UniqueConstraint("user_id", "module", name="uq_shares_user_module"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户ID（FK users.id，登录态隔离）")
    module: Mapped[str] = mapped_column(String(32), index=True, comment="模块标识：tarot / bugua / dream")
    title: Mapped[str] = mapped_column(String(128), default="", comment="分享标题/关键词（如牌阵名、梦境主题）")
    share_text: Mapped[str] = mapped_column(String(4096), default="", comment="分享文案")
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="配图URL（CogView 生成，可能为空）")
    image_prompt: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="配图提示词（生成失败时为 None）")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def userId(self) -> int:
        """camelCase 别名：供 Pydantic from_attributes 序列化使用。"""
        return self.user_id
