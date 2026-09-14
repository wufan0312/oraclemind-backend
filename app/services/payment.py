"""随喜供养支付渠道适配层（#1）。

设计：统一 ``PaymentChannel`` 协议，当前两个实现——

- ``StubChannel``：未配置微信商户号时的降级渠道。返回一个占位 pay_url，
  前端据此展示「支付通道配置中」的引导，整个下单→轮询→成功页链路依然完整可跑，
  配置凭证后无需改动任何业务代码即可切到真实支付。
- ``WechatNativeChannel``：微信支付 Native（扫码）下单。需要
  ``WECHAT_MCH_ID / WECHAT_APP_ID / WECHAT_API_V3_KEY / WECHAT_SERIAL_NO`` 与商户私钥证书。

安全说明：真实渠道的下单与回调校验涉及 RSA 签名与平台证书解密，属高风险代码路径。
本项目当前未配置商户号，故 ``WechatNativeChannel.create_order`` 显式抛 NotImplementedError，
避免出现「看起来能支付、实际没签名」的假实现。
R8 关联：支付回调（/premium/notify、/donations/notify）已由 S1 加 ``X-Payment-Token`` 鉴权兜底；
``create_order`` 抛出的 NotImplementedError 由 ``create_order_with_fallback`` 捕获并降级为 StubChannel，
不会出现未验签即落单或把异常栈泄露给客户端的情况。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class ChannelResult:
    """渠道下单结果。"""

    channel: str
    pay_url: str | None
    qr_text: str
    message: str


class PaymentChannel(Protocol):
    """支付渠道协议。"""

    name: str

    def create_order(self, out_trade_no: str, amount_fen: int, description: str) -> ChannelResult:
        """向渠道下单，返回支付链接/收款码。"""
        ...


class StubChannel:
    """占位渠道：凭证未配置时使用，保证链路可跑通但不产生真实交易。"""

    name = "stub"

    def create_order(self, out_trade_no: str, amount_fen: int, description: str) -> ChannelResult:
        amount = (Decimal(amount_fen) / 100).quantize(Decimal("0.01"))
        return ChannelResult(
            channel=self.name,
            pay_url=None,
            qr_text=f"玄镜随喜供养 ¥{amount}",
            message=(
                "支付通道正在接入中，当前订单已记录，可完整免费查看报告 🙏。"
                "（配置微信商户号后自动启用真实支付）"
            ),
        )


class WechatNativeChannel:
    """微信支付 Native 扫码渠道。

    真实实现需要：商户私钥证书（apiclient_key.pem）做 RSA-SHA256 签名、
    平台证书解密回调、证书序列号与 APIv3 密钥。为避免交付「未经验证的签名逻辑」，
    在证书与签名链路就绪前保持 NotImplementedError，调用方会捕获并降级到 StubChannel。
    """

    name = "wechat"

    def __init__(self, mch_id: str, app_id: str, api_v3_key: str, serial_no: str) -> None:
        self.mch_id = mch_id
        self.app_id = app_id
        self.api_v3_key = api_v3_key
        self.serial_no = serial_no

    def create_order(self, out_trade_no: str, amount_fen: int, description: str) -> ChannelResult:
        raise NotImplementedError(
            "微信支付 Native 下单需要商户私钥证书签名链路，尚未启用；"
            "请先在 app/services/payment/wechat_sign.py 补齐 RSA 签名与平台证书校验。"
        )


def build_out_trade_no() -> str:
    """生成商户订单号：OM + 时间戳 + 8 位随机，保证可读且难以碰撞。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"OM{stamp}{uuid.uuid4().hex[:8].upper()}"


def default_expire_at(minutes: int) -> datetime:
    """订单过期时间（UTC 带时区，与 ORM DateTime(timezone=True) 对齐）。"""
    return datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))


def get_channel() -> PaymentChannel:
    """按配置选择渠道：凭证齐备则微信 Native，否则降级 stub。"""
    from app.core.config import settings

    if settings.wechat_pay_enabled:
        try:
            return WechatNativeChannel(
                mch_id=settings.wechat_mch_id,
                app_id=settings.wechat_app_id,
                api_v3_key=settings.wechat_api_v3_key,
                serial_no=settings.wechat_serial_no,
            )
        except Exception as exc:  # pragma: no cover - 配置异常路径
            logger.warning("微信支付渠道初始化失败，降级 stub：%s", exc)
    return StubChannel()


def create_order_with_fallback(
    channel: PaymentChannel, out_trade_no: str, amount_fen: int, description: str
) -> ChannelResult:
    """下单并在真实渠道不可用时降级 stub，保证用户侧流程不中断。"""
    try:
        return channel.create_order(out_trade_no, amount_fen, description)
    except NotImplementedError as exc:
        logger.info("渠道 %s 暂不可用，降级 stub：%s", channel.name, exc)
        return StubChannel().create_order(out_trade_no, amount_fen, description)
