"""用户资料模型 —— 存储用户出生信息与偏好设置。

与 User 表一对一关系，避免在认证表上堆业务字段。
开发环境使用 SQLite，生产环境切回 PostgreSQL。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserProfile(Base):
    """用户资料：出生信息 + 偏好设置（与 User 一对一）。"""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        comment="关联用户 ID（唯一，实现一对一）",
    )

    # ===== 出生信息（聚合为 JSON，与前端 VisitorBirth / BirthInfo 一一对应）=====
    # 统一存为 JSON 对象：{date,time,gender,lunarYear,lunarMonth,lunarDay,province,city,lat,lng}
    # 透明加密：应用层（app/api/v1/profile.py）写库前 encrypt_value、读库后 decrypt_value
    # （对应缺陷报告 P0-4）。DB 中以密文 TEXT（enc:: 前缀）落地；旧明文 JSON 也兼容读取。
    birth: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="出生信息聚合 JSON（加密存储：date/time/gender/lunarYear/lunarMonth/lunarDay/province/city/lat/lng）"
    )

    # ===== 偏好设置 =====
    timezone: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="Asia/Shanghai", comment="时区"
    )
    theme: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="主题偏好")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户备注")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)
