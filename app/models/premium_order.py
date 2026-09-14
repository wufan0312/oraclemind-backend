"""进阶内容付费订单模型 —— 付费墙（塔罗深度 / 占星完整 / 全站通卡）。

与 donation_orders 的区别：
- donation_orders 是「随喜供养」，金额自由、无商品概念；
- premium_orders 是「明码标价的商品订单」，**记录商品标识 item_id**（对账可按商品维度
  统计，而不是像供养那样只能按金额猜），并可绑定生效范围（ref_type / ref_id，
  例如「单次塔罗深度解读」只对这一局牌面生效）。

设计要点：
- 金额以「分」存整数，且**服务端按商品目录定价**，不信任客户端传值（防篡改）；
- 支付渠道可插拔，复用 app.services.payment：未配微信商户号时走 stub（占位引导），
  配齐 WECHAT_MCH_ID / APP_ID / API_V3_KEY / SERIAL_NO 后自动切真实支付，业务代码零改动；
- 状态机 pending → paid / failed / expired，只允许 pending 单向流转，回调幂等；
- self_claimed：个人收款码（无自动回调）场景下用户自报已付，仅供人工对账，
  **不视为 paid**，权益发放只认 status=paid。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PremiumOrder(Base):
    """进阶内容付费订单。"""

    __tablename__ = "premium_orders"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    out_trade_no: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="商户订单号（幂等键，前端轮询与回调都用它）"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True, index=True, comment="登录用户ID"
    )
    visitor_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="访客ID（匿名下单归属）")
    owner_type: Mapped[str] = mapped_column(
        String(8), default="visitor", server_default="visitor", comment="归属：visitor / user"
    )
    # ===== 商品标识（对账核心：区别于 donation_orders 只有金额）=====
    item_id: Mapped[str] = mapped_column(
        String(32), index=True, comment="商品ID：tarot_deep / astro_full / all_access"
    )
    item_name: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="商品名快照（下单时固定）")
    amount_fen: Mapped[int] = mapped_column(Integer, comment="应付金额（单位：分，服务端按目录定价）")
    # ===== 生效范围（单次解锁类商品绑定具体对象）=====
    ref_type: Mapped[str] = mapped_column(
        String(32), default="", server_default="", comment="关联对象类型：tarot_spread / report / horoscope"
    )
    ref_id: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="关联对象ID（如这一局的牌面ID/报告ID）"
    )
    channel: Mapped[str] = mapped_column(
        String(16), default="stub", server_default="stub", comment="支付渠道：wechat / stub"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True,
        comment="订单状态：pending / paid / failed / expired",
    )
    pay_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="收款码/支付链接（stub 渠道为 None）"
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="渠道交易号（微信支付回调返回）"
    )
    # 个人收款码无自动回调：用户点「我已完成支付」后留痕，供人工按核对码对账（不发权益）
    self_claimed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", comment="用户是否自报已付（仅对账用，不视为已支付）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付完成时间")
    # 订单有效期：默认 30 分钟未支付自动过期（查询侧惰性判定，无需定时任务）
    expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="订单过期时间（超过则视为 expired）"
    )
