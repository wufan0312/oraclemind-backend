"""前端业务数据上云存储（缺陷报告 P1-8）。

把原先只落在 localStorage 的核心业务数据（排盘缓存、对话历史、梦境日记、
修行存档、塔罗/命理历史、跨页占卜等）同步到后端，使其：
- 清除浏览器数据 / 换设备 / 换浏览器 后可恢复；
- 隐私模式也能持久化；
- localStorage 退化为离线缓存，不再承担唯一数据源。

身份隔离沿用 reports 的 owner 模型：
- 登录态：owner_key = ``user:{user_id}``
- 匿名态：owner_key = ``visitor:{visitor_id}``

``(owner_key, key)`` 唯一，写入走 INSERT ... ON CONFLICT DO UPDATE 原子 upsert。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserStash(Base):
    """前端上云 KV 存储：每个身份一份命名空间。"""

    __tablename__ = "user_stash"

    __table_args__ = (UniqueConstraint("owner_key", "key", name="uq_stash_owner_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 身份键：user:{id} / visitor:{visitor_id}，写入端构造
    owner_key: Mapped[str] = mapped_column(String(96), index=True, comment="身份键：user:{id} / visitor:{visitor_id}")
    key: Mapped[str] = mapped_column(String(128), comment="数据键（与前端 localStorage key 对齐）")
    value: Mapped[str] = mapped_column(Text, comment="JSON 序列化的业务数据")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
