"""支付回调鉴权（P0 修复：防伪造 success 免费解锁付费权益）。

背景：/premium/notify 与 /donations/notify 在 stub 渠道（当前实际唯一渠道）下原本无任何鉴权，
攻击者可伪造 success:true 将订单置 paid，从而通过 entitlements 免费解锁付费内容。

规则：
- 已配置 PAYMENT_CALLBACK_SECRET：回调必须携带匹配令牌（header X-Payment-Token），
  缺失或错误 → 401，且调用方**不得**处理订单（绝不信任 payload.success）。
- 未配置 PAYMENT_CALLBACK_SECRET：
  - 生产环境（APP_ENV=production）→ 403（生产必须配置回调鉴权或启用真实微信验签），不处理订单。
  - 开发环境 → 放行（记 warning），维持本地测试便利。

真实微信支付接入时，应在各 notify 内再补 Wechatpay-Signature 验签（平台证书/时间戳/随机数
并解密 resource），验签通过前同样不得信任 success。本模块仅覆盖「通用回调令牌」这一层。
"""

import hmac
import logging

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

CALLBACK_TOKEN_HEADER = "X-Payment-Token"


def verify_notify_auth(token: str | None) -> None:
    """校验支付回调令牌；不通过则抛 401/403，调用方不得继续处理订单。

    使用 hmac.compare_digest 做常量时间比较，避免时序侧信道。
    """
    secret = settings.payment_callback_secret
    if secret:
        if not token or not hmac.compare_digest(token, secret):
            logger.warning("支付回调鉴权失败：令牌缺失或错误（已拒绝，未信任 payload.success）")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="支付回调鉴权失败",
            )
        return

    # 未配置回调秘密
    if settings.is_production:
        logger.warning("生产环境支付回调未配置 PAYMENT_CALLBACK_SECRET，已拒绝（防伪造 success）")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="生产环境支付回调必须配置 PAYMENT_CALLBACK_SECRET 或启用微信验签",
        )
    logger.warning(
        "支付回调未鉴权（dev 放行）：生产环境必须配置 PAYMENT_CALLBACK_SECRET，否则回调接口对任何人开放"
    )
