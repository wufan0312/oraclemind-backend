"""用户模型 —— 用户名/密码认证。

开发环境使用 SQLite，生产环境切回 PostgreSQL（仅改 DATABASE_URL）。
密码哈希使用 passlib pbkdf2_sha256（纯 Python，免 C 编译依赖）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """注册用户：用户名 + 密码哈希 + 可选邮箱。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录用户名")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="邮箱（可选）")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希（pbkdf2_sha256）")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="软删时间戳（合规：账号注销走软删）",
    )
    # 后台管理：封禁（§3 用户管理）
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", comment="是否被封禁"
    )
    banned_reason: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="封禁原因"
    )
    banned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="封禁时间"
    )
