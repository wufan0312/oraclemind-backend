"""随喜供养订单模型 —— 支付域 orders 的简化落地。

设计要点：
- 与 reports 同库，但归属规则一致（owner_type + user_id / visitor_id）；
- amount_fen 以「分」为单位存整数，杜绝浮点误差（¥19.9 → 1990）；
- 支付渠道可插拔：channel 记录 wechat / stub，channel 未配置真实商户号时
  走 stub（返回占位收款码 + 引导文案），填入凭证后无需改表即可切到真实支付；
- 状态机：pending → paid / failed / expired，只允许 pending 单向流转，
  重复回调幂等（同一 out_trade_no 只生效一次）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DonationOrder(Base):
    """随喜供养订单。"""

    __tablename__ = "donation_orders"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    out_trade_no: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="商户订单号（幂等键，前端轮询与回调都用它）"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True, comment="登录用户ID"
    )
    visitor_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="访客ID（匿名供养归属）")
    owner_type: Mapped[str] = mapped_column(
        String(8), default="visitor", server_default="visitor", comment="归属：visitor / user"
    )
    amount_fen: Mapped[int] = mapped_column(Integer, comment="供养金额（单位：分）")
    tier: Mapped[str] = mapped_column(String(32), default="", comment="档位名：心意 / 诚意 / 大愿 / 自定义")
    channel: Mapped[str] = mapped_column(
        String(16), default="stub", server_default="stub", comment="支付渠道：wechat / stub"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True,
        comment="订单状态：pending / paid / failed / expired",
    )
    pay_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="收款码/支付链接（stub 渠道为占位说明）"
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="渠道交易号（微信支付回调返回）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付完成时间")
    # 订单有效期：默认 30 分钟未支付自动过期（查询侧惰性判定，无需定时任务）
    expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="订单过期时间（超过则视为 expired）"
    )
