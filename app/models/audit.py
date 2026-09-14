"""审计日志模型 —— 记录关键写操作（登录/注册/排盘保存/分享）。

满足 §4.6 合规三件套之二：审计日志至少保留 1 年。
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """审计日志：所有关键写操作落库。

    - action: 动作类型（login/register/create_report/delete_report/share_upsert/pii_reminder_due ...）
    - actor_type: 操作者类型（user/visitor/system）
    - actor_id: 操作者标识（用户 id 或访客 id）
    - target: 操作对象（如 report.id / module 名）
    - detail: 操作上下文（IP/UA/参数摘要等，按需脱敏）
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    action: Mapped[str] = mapped_column(String(64), index=True, comment="动作类型")
    actor_type: Mapped[str] = mapped_column(
        String(16), default="user", server_default="user", comment="操作者类型：user/visitor/system"
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="操作者标识（用户ID或访客ID）"
    )
    target: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="操作对象")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="操作上下文（按需脱敏）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
