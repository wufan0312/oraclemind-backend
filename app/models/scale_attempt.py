"""量表作答持久化模型 —— 右轨心理学产品的作答留存（2026-09-20）。

与 /assessment（复原力测评）的纯前端 localStorage 留存不同，量表作答需服务端落库：
- 同一份作答（answers）与计分结果（score_json）一并保存，便于后续 AI 心理报告
  直接以服务端计分结果为准（不依赖前端重传），也为个人中心「查看 / 删除」提供真源；
- 归属复用 premium_orders 的 visitor / user 双轨：登录用户按账号隔离，匿名按 visitorId 隔离；
- answers_json / score_json 用 JSON 列（PostgreSQL 原生 JSON，SQLite 存文本），服务端权威，
  前端只上送 {题ID: 1-5}，无法篡改计分（计分在 score_scale 完成后再存）。
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScaleAttempt(Base):
    """量表作答记录（一次完整测评的快照）。"""

    __tablename__ = "scale_attempts"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    # 量表标识（slug 即 scale_catalog 的键）
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="量表 slug")
    # 归属：登录用户按 user_id，匿名按 visitor_id；二者皆空时落 anonymous（仍可留存）
    user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True, comment="登录用户ID"
    )
    visitor_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="访客ID（匿名归属）")
    owner_type: Mapped[str] = mapped_column(
        String(8), default="visitor", server_default="visitor", comment="归属：user / visitor / anonymous"
    )
    # 作答原文（{题ID: 1-5}）—— 服务端已校验完整性与取值
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="作答：{题ID: 1-5}")
    # 计分结果（维度分 + 等级 + 解读），结构与 ScaleScoreResult.dimensions 对齐
    score_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="计分结果：维度分列表")
    # 服务端综合觉察摘要（score_scale 生成）
    summary: Mapped[str] = mapped_column(Text, default="", server_default="", comment="综合觉察摘要")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="作答时间")
