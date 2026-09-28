"""随喜供养 Pydantic 模型（#1：订单流程 + 可插拔支付渠道）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import is_valid_visitor_id

# 允许的三档（单位：分）。前端定价卡与之对应，服务端二次校验，
# 防止客户端篡改金额（如改成 1 分或 999999 分）。
TIERS: dict[str, int] = {
    "心意": 660,
    "诚意": 1990,
    "大愿": 6600,
}
MIN_AMOUNT_FEN = 100  # ¥1 起
MAX_AMOUNT_FEN = 200000  # ¥2000 上限，挡住误操作与恶意大额


class DonationCreate(BaseModel):
    """创建供养订单。"""

    tier: str = Field(default="诚意", max_length=32, description="档位：心意 / 诚意 / 大愿 / 自定义")
    amountFen: int | None = Field(default=None, ge=MIN_AMOUNT_FEN, le=MAX_AMOUNT_FEN, description="自定义金额（分），tier=自定义 时必填")
    visitorId: str | None = Field(default=None, max_length=64, description="访客ID（匿名时必填）")
    approvalId: int | None = Field(
        default=None, description="审批 Gate 的 approval_id（P1 Human-in-the-loop）；不传则按原流程下单"
    )

    @field_validator("tier")
    @classmethod
    def _check_tier(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in TIERS and s != "自定义":
            raise ValueError("档位不合法")
        return s

    @field_validator("visitorId")
    @classmethod
    def _check_visitor_id(cls, v: str | None) -> str | None:
        # S9 加固：匿名身份凭证格式校验，防止异常值绕过隔离。
        # 登录用户可省略（落空串），空串视为「无访客」放行；仅拒绝非空的非法值。
        if v is not None and v != "" and not is_valid_visitor_id(v):
            raise ValueError("visitorId 格式非法")
        return v

    def resolve_amount(self) -> int:
        """解析最终金额（分）：固定档位直接用预设值，自定义档位用 amountFen。"""
        if self.tier in TIERS:
            return TIERS[self.tier]
        if self.amountFen is None:
            raise ValueError("自定义档位必须提供 amountFen")
        return self.amountFen


class DonationOut(BaseModel):
    """订单详情（含支付引导）。"""

    model_config = ConfigDict(from_attributes=True)

    outTradeNo: str
    tier: str = ""
    amountFen: int
    amountYuan: str
    channel: str
    status: str
    payUrl: str | None = None
    qrText: str = ""
    createdAt: datetime
    expireAt: datetime
    paidAt: datetime | None = None
    message: str = ""


class DonationNotify(BaseModel):
    """支付渠道回调（幂等：同一 out_trade_no 重复回调只生效一次）。

    注意：本模型不含 ``sign`` 字段——回调鉴权统一由 ``X-Payment-Token`` 头（S1/P0 修复，
    ``verify_notify_auth``）承载，真实微信支付接入时在 ``notify`` 路由内补 Wechatpay-Signature
    验签即可。保留一个永不消费的 ``sign`` 字段会造成「已验签」错觉，故删除（Q1）。
    """

    outTradeNo: str = Field(..., max_length=64, description="商户订单号")
    transactionId: str | None = Field(default=None, max_length=128, description="渠道交易号")
    success: bool = Field(..., description="支付是否成功")
