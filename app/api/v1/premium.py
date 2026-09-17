"""进阶内容付费 API（付费墙）—— 商品目录 / 下单 / 轮询 / 回调 / 权益。

与 /donations（随喜供养）的分工：
- donations：金额自由、无商品概念，用于随喜供养；
- premium：明码标价的商品订单，**记录 item_id**，支持单次解锁绑定（ref_type/ref_id），
  并对外提供 `GET /premium/entitlements` 作为权益发放的**服务端真源**。

渠道可插拔（复用 app.services.payment）：
- 未配置微信商户号 → stub：下单只记意图，前端展示占位卡/个人收款码，不产生真实交易；
- 配齐 WECHAT_MCH_ID / APP_ID / API_V3_KEY / SERIAL_NO → 自动切微信 Native 扫码，
  回调写 paid → entitlements 立刻生效，**业务代码零改动**。

安全：
- 金额来自服务端商品目录，客户端只传 itemId；
- 订单查询/自报均做归属校验，不匹配返回 404（不泄露订单存在性）；
- 回调按 out_trade_no 幂等，已支付订单重复回调不重复记账。
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
from app.models.premium_order import PremiumOrder
from app.models.user import User
from app.schemas.premium import (
    FREE_PERKS,
    PREMIUM_CATALOG,
    PremiumEntitlementItem,
    PremiumEntitlementsOut,
    PremiumNotify,
    PremiumOrderCreate,
    PremiumOrderOut,
    PremiumPlanOut,
    PremiumPlansOut,
    get_item,
)
from app.services.payment import (
    build_out_trade_no,
    create_order_with_fallback,
    default_expire_at,
    get_channel,
)

router = APIRouter(tags=["进阶内容付费"])


def _amount_yuan(fen: int) -> str:
    return f"{fen / 100:.2f}"


def _to_out(o: PremiumOrder, message: str = "") -> PremiumOrderOut:
    item = get_item(o.item_id)
    return PremiumOrderOut(
        outTradeNo=o.out_trade_no,
        itemId=o.item_id,
        itemName=o.item_name or (item.name if item else o.item_id),
        amountFen=o.amount_fen,
        amountYuan=_amount_yuan(o.amount_fen),
        channel=o.channel,
        status=o.status,
        payUrl=o.pay_url,
        qrText=(o.pay_url or f"玄镜 · {o.item_name or o.item_id} ¥{_amount_yuan(o.amount_fen)}"),
        # 个人收款码人工对账用的核对码（订单号后 8 位，前端可直接展示）
        checkCode=o.out_trade_no[-8:],
        refType=o.ref_type or "",
        refId=o.ref_id or "",
        selfClaimed=bool(o.self_claimed),
        createdAt=o.created_at,
        expireAt=o.expire_at,
        paidAt=o.paid_at,
        message=message,
    )


def _expire_if_needed(o: PremiumOrder) -> None:
    """惰性过期：超过 expire_at 的 pending 订单标记为 expired（无需定时任务）。"""
    if o.status != "pending":
        return
    now = datetime.now(timezone.utc)
    exp = o.expire_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now > exp:
        o.status = "expired"


async def _load_owned_order(
    db: AsyncSession,
    out_trade_no: str,
    user: User | None,
    visitor_id: str | None,
) -> PremiumOrder:
    """按订单号取单并校验归属；不匹配一律 404（不泄露订单存在性）。"""
    order = (
        await db.execute(select(PremiumOrder).where(PremiumOrder.out_trade_no == out_trade_no))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if user is not None:
        if order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    elif visitor_id:
        if order.visitor_id != visitor_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


@router.get("/premium/plans", response_model=PremiumPlansOut, summary="付费商品目录")
async def list_plans() -> PremiumPlansOut:
    """商品与价格由服务端下发（前端无需硬编码，改价不重启前端）。"""
    return PremiumPlansOut(
        plans=[
            PremiumPlanOut(
                itemId=it.item_id,
                name=it.name,
                icon=it.icon,
                priceFen=it.price_fen,
                priceYuan=_amount_yuan(it.price_fen),
                tagline=it.tagline,
                perks=list(it.perks),
                scope=it.scope,
            )
            for it in PREMIUM_CATALOG.values()
        ],
        freePerks=list(FREE_PERKS),
        channel=get_channel().name,
    )


@router.post("/premium/orders", response_model=PremiumOrderOut, status_code=status.HTTP_201_CREATED, summary="创建付费订单")
async def create_premium_order(
    payload: PremiumOrderCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> PremiumOrderOut:
    """下单并获取支付引导；金额按服务端目录解析，客户端传值仅作参考（金额不采信）。"""
    require_identity(user, payload.visitorId)
    item = get_item(payload.itemId)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"商品不存在：{payload.itemId}（可选：{', '.join(PREMIUM_CATALOG)}）",
        )
    # 合规重定位（2026-09-17）：占卜类商品暂停销售，切断「获利引流」合规要件
    PAUSED_ITEMS = {"tarot_deep", "astro_full", "all_access"}
    if item.item_id in PAUSED_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该商品已暂停销售，全部基础功能永久免费可用 🙏",
        )

    out_trade_no = build_out_trade_no()
    channel = get_channel()
    result = create_order_with_fallback(channel, out_trade_no, item.price_fen, f"玄镜 · {item.name}")

    order = PremiumOrder(
        out_trade_no=out_trade_no,
        user_id=user.id if user is not None else None,
        visitor_id=payload.visitorId or "",
        owner_type="user" if user is not None else "visitor",
        item_id=item.item_id,
        item_name=item.name,
        amount_fen=item.price_fen,
        ref_type=(payload.refType or "").strip(),
        ref_id=(payload.refId or "").strip(),
        channel=result.channel,
        status="pending",
        pay_url=result.pay_url,
        expire_at=default_expire_at(settings.donation_expire_minutes),
    )
    db.add(order)
    await db.flush()
    await audited_commit(
        db,
        "create_premium_order",
        actor_type=order.owner_type,
        actor_id=actor_id_of(user, payload.visitorId),
        target=f"{out_trade_no}:{item.item_id}",
    )
    await db.refresh(order)
    return _to_out(order, result.message)


@router.get("/premium/orders/{out_trade_no}", response_model=PremiumOrderOut, summary="查询订单状态（前端轮询）")
async def get_premium_order(
    out_trade_no: str,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> PremiumOrderOut:
    """轮询订单状态；归属不匹配返回 404。"""
    order = await _load_owned_order(db, out_trade_no, user, visitorId)
    _expire_if_needed(order)
    if order.status == "expired":
        await db.commit()
    message = ""
    if order.status == "pending" and order.channel == "stub":
        message = "支付通道正在接入中，当前订单已记录，可完整免费查看 🙏。"
    elif order.status == "paid":
        message = "支付成功，权益已生效 🙏"
    elif order.status == "expired":
        message = "订单已过期，可重新发起。"
    return _to_out(order, message)


@router.post("/premium/orders/{out_trade_no}/claim", response_model=PremiumOrderOut, summary="用户自报已付（个人收款码对账）")
async def claim_premium_paid(
    out_trade_no: str,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> PremiumOrderOut:
    """个人收款码无自动回调：用户点「我已完成支付」时留痕。

    只写 self_claimed=1 供人工对账，**不置为 paid、不发服务端权益**
    （前端本地解锁是为了不卡住用户，服务端权益仍以真实回调为准）。
    """
    order = await _load_owned_order(db, out_trade_no, user, visitorId)
    _expire_if_needed(order)
    if order.status == "paid":
        return _to_out(order, "订单已支付，权益已生效 🙏")
    order.self_claimed = True
    await audited_commit(
        db,
        "claim_premium_paid",
        actor_type=order.owner_type,
        actor_id=actor_id_of(user, visitorId),
        target=out_trade_no,
    )
    await db.refresh(order)
    return _to_out(order, "已收到你的付款反馈，我们会按核对码人工对账，感谢支持 🙏")


@router.post("/premium/notify", response_model=dict, summary="支付结果回调")
async def notify_premium(
    payload: PremiumNotify,
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
        await db.execute(select(PremiumOrder).where(PremiumOrder.out_trade_no == payload.outTradeNo))
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


@router.get("/premium/entitlements", response_model=PremiumEntitlementsOut, summary="查询已解锁权益")
async def get_entitlements(
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> PremiumEntitlementsOut:
    """服务端权益真源：只认 status=paid 的订单，全站通卡折算为全解锁。"""
    require_identity(user, visitorId)
    if user is not None:
        stmt = select(PremiumOrder).where(PremiumOrder.user_id == user.id, PremiumOrder.status == "paid")
    elif visitorId:
        stmt = select(PremiumOrder).where(PremiumOrder.visitor_id == visitorId, PremiumOrder.status == "paid")

    orders = (await db.execute(stmt.order_by(PremiumOrder.paid_at.desc()))).scalars().all()

    items: list[PremiumEntitlementItem] = []
    unlocked: set[str] = set()
    covers_all = False
    seen: set[str] = set()
    for o in orders:
        unlocked.add(o.item_id)
        item = get_item(o.item_id)
        if item is not None and item.covers_all:
            covers_all = True
        if o.item_id in seen:
            continue
        seen.add(o.item_id)
        items.append(
            PremiumEntitlementItem(
                itemId=o.item_id,
                unlocked=True,
                orderNo=o.out_trade_no,
                channel=o.channel,
                paidAt=o.paid_at,
                refType=o.ref_type or "",
                refId=o.ref_id or "",
            )
        )

    if covers_all:
        unlocked = set(PREMIUM_CATALOG.keys())

    return PremiumEntitlementsOut(
        visitorId=visitorId or "",
        userId=user.id if user is not None else None,
        unlocked=sorted(unlocked),
        items=items,
        channel=get_channel().name,
    )
