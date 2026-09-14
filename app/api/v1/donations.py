"""随喜供养 API（#1）—— 下单 → 引导支付 → 轮询 → 成功页。

渠道可插拔：未配置微信商户号时走 stub（占位引导，不产生真实交易），
配置凭证后自动切到微信 Native 扫码支付，业务代码无需改动。

安全：
- 金额服务端二次校验（三档固定值 + 自定义区间），不信任客户端传值；
- 回调按 out_trade_no 幂等，已支付订单重复回调不重复记账；
- 查询接口只返回订单自身状态，不泄露他人订单（归属校验后返回 404）。
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_optional_user, get_visitor_id
from app.core.audit import audited_commit
from app.core.config import settings
from app.core.ownership import actor_id_of, require_identity
from app.core.payment_security import CALLBACK_TOKEN_HEADER, verify_notify_auth
from app.db.session import get_db
from app.models.donation_order import DonationOrder
from app.models.user import User
from app.schemas.donation import DonationCreate, DonationNotify, DonationOut
from app.services.payment import (
    build_out_trade_no,
    create_order_with_fallback,
    default_expire_at,
    get_channel,
)

router = APIRouter(tags=["随喜供养"])


def _amount_yuan(fen: int) -> str:
    return f"{fen / 100:.2f}"


def _to_out(o: DonationOrder, message: str = "") -> DonationOut:
    return DonationOut(
        outTradeNo=o.out_trade_no,
        tier=o.tier or "",
        amountFen=o.amount_fen,
        amountYuan=_amount_yuan(o.amount_fen),
        channel=o.channel,
        status=o.status,
        payUrl=o.pay_url,
        qrText=(o.pay_url or f"玄镜随喜供养 ¥{_amount_yuan(o.amount_fen)}"),
        createdAt=o.created_at,
        expireAt=o.expire_at,
        paidAt=o.paid_at,
        message=message,
    )


def _expire_if_needed(o: DonationOrder) -> None:
    """惰性过期：超过 expire_at 的 pending 订单标记为 expired（无需定时任务）。"""
    if o.status != "pending":
        return
    now = datetime.now(timezone.utc)
    exp = o.expire_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now > exp:
        o.status = "expired"


@router.post("/donations", response_model=DonationOut, status_code=status.HTTP_201_CREATED, summary="创建供养订单")
async def create_donation(
    payload: DonationCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DonationOut:
    """下单并获取支付引导；金额由服务端按档位解析，客户端传值仅作参考。"""
    require_identity(user, payload.visitorId)
    try:
        amount_fen = payload.resolve_amount()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    out_trade_no = build_out_trade_no()
    channel = get_channel()
    result = create_order_with_fallback(
        channel, out_trade_no, amount_fen, f"玄镜随喜供养 · {payload.tier}"
    )

    order = DonationOrder(
        out_trade_no=out_trade_no,
        user_id=user.id if user is not None else None,
        visitor_id=payload.visitorId or "",
        owner_type="user" if user is not None else "visitor",
        amount_fen=amount_fen,
        tier=payload.tier,
        channel=result.channel,
        status="pending",
        pay_url=result.pay_url,
        expire_at=default_expire_at(settings.donation_expire_minutes),
    )
    db.add(order)
    await db.flush()
    await audited_commit(
        db,
        "create_donation",
        actor_type=order.owner_type,
        actor_id=actor_id_of(user, payload.visitorId),
        target=out_trade_no,
    )
    await db.refresh(order)
    return _to_out(order, result.message)


@router.get("/donations/{out_trade_no}", response_model=DonationOut, summary="查询订单状态（前端轮询）")
async def get_donation(
    out_trade_no: str,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> DonationOut:
    """轮询订单状态；归属不匹配返回 404（不泄露订单存在性）。"""
    order = (
        await db.execute(select(DonationOrder).where(DonationOrder.out_trade_no == out_trade_no))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if user is not None:
        if order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    elif visitorId:
        if order.visitor_id != visitorId:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")

    _expire_if_needed(order)
    if order.status == "expired":
        await db.commit()
    message = ""
    if order.status == "pending" and order.channel == "stub":
        message = "支付通道正在接入中，当前订单已记录，可完整免费查看报告 🙏。"
    elif order.status == "paid":
        message = "感恩供养，功德无量 🙏"
    elif order.status == "expired":
        message = "订单已过期，可重新发起供养。"
    return _to_out(order, message)


@router.post("/donations/notify", response_model=dict, summary="支付结果回调")
async def notify_donation(
    payload: DonationNotify,
    x_token: str | None = Header(default=None, alias=CALLBACK_TOKEN_HEADER),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """渠道回调：按 out_trade_no 幂等更新。

    P0 安全修复：必须先通过回调令牌鉴权（header X-Payment-Token，值=PAYMENT_CALLBACK_SECRET），
    缺失/不匹配直接拒绝，且**绝不信任 payload.success**。

    真实微信支付接入时需在此补 Wechatpay-Signature 验签（平台证书/时间戳/随机数并解密 resource），
    验签通过前同样不得信任 success；当前 stub 渠道不会触发真实回调。
    `payload.sign` 仅供真实微信验签消费，本令牌模式下不参与鉴权。
    """
    verify_notify_auth(x_token)
    order = (
        await db.execute(select(DonationOrder).where(DonationOrder.out_trade_no == payload.outTradeNo))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status == "paid":
        return {"ok": True, "status": order.status, "duplicate": True}
    # 防付费墙绕过：过期 pending 单即使收到成功回调也保持 expired，绝不置 paid
    _expire_if_needed(order)
    if order.status == "expired":
        await db.commit()
        return {"ok": True, "status": "expired", "expired": True}
    if payload.success:
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        order.transaction_id = payload.transactionId
        await db.commit()
        return {"ok": True, "status": "paid", "duplicate": False}
    order.status = "failed"
    await db.commit()
    return {"ok": True, "status": "failed", "duplicate": False}
