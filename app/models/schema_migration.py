"""迁移版本追踪表 —— 记录已执行的幂等迁移（缺陷报告 P0-3 的轻量解法）。

现状：init_db._migrate_* 已实现 inspector 探测 + 条件 ALTER 的幂等迁移，跨库安全，
但缺乏「历史追踪」。本表登记每次迁移的版本名，使迁移可审计、可重复应用判定，
弥补手写迁移「无法追踪迁移历史」的短板（回滚由手动脚本处理，原型期可接受）。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaMigration(Base):
    """已应用的数据库迁移记录（轻量版 alembic 版本表）。"""

    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="迁移版本名（如 birth_to_json_v1）"
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="应用时间"
    )
