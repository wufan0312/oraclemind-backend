"""支付回调过期防护回归测试（高优先级 #1：防付费墙绕过）。

验证 notify 在已支付短路之后、success 分支之前，必须先惰性过期：
- 过期 pending 订单收到 success 回调 → 保持 status=expired，绝不置 paid
  （stub 渠道不触发真实回调，但微信接入后重放过期单的 success 将绕过付费墙）
- 未过期 pending 订单收到 success 回调 → 正常置 paid（修复不破坏正常付费）
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.donations import notify_donation
from app.api.v1.premium import notify_premium
from app.core.config import settings
from app.models.donation_order import DonationOrder
from app.models.premium_order import PremiumOrder
from app.schemas.donation import DonationNotify
from app.schemas.premium import PremiumNotify


@pytest.fixture
def _dev_no_secret():
    orig_secret = settings.payment_callback_secret
    orig_env = settings.app_env
    settings.payment_callback_secret = ""
    settings.app_env = "development"
    try:
        yield
    finally:
        settings.payment_callback_secret = orig_secret
        settings.app_env = orig_env


def _make_db_mock(order):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = order
    db.execute.return_value = result
    db.commit = AsyncMock()
    return db


# ---- premium ----
def test_expired_premium_order_not_marked_paid(_dev_no_secret):
    order = PremiumOrder(
        out_trade_no="PREM_EXP_1",
        status="pending",
        expire_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db = _make_db_mock(order)
    payload = PremiumNotify(outTradeNo="PREM_EXP_1", success=True, transactionId="txn1")
    res = asyncio.run(notify_premium(payload, x_token=None, db=db))
    assert res["status"] == "expired"
    assert res.get("expired") is True
    assert order.status == "expired"
    db.commit.assert_awaited()


def test_valid_pending_premium_marked_paid(_dev_no_secret):
    order = PremiumOrder(
        out_trade_no="PREM_OK_1",
        status="pending",
        expire_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    db = _make_db_mock(order)
    payload = PremiumNotify(outTradeNo="PREM_OK_1", success=True, transactionId="txn2")
    res = asyncio.run(notify_premium(payload, x_token=None, db=db))
    assert res["status"] == "paid"
    assert order.status == "paid"
    db.commit.assert_awaited()


# ---- donations ----
def test_expired_donation_order_not_marked_paid(_dev_no_secret):
    order = DonationOrder(
        out_trade_no="DON_EXP_1",
        status="pending",
        expire_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db = _make_db_mock(order)
    payload = DonationNotify(outTradeNo="DON_EXP_1", success=True, transactionId="txn1")
    res = asyncio.run(notify_donation(payload, x_token=None, db=db))
    assert res["status"] == "expired"
    assert res.get("expired") is True
    assert order.status == "expired"
    db.commit.assert_awaited()


def test_valid_pending_donation_marked_paid(_dev_no_secret):
    order = DonationOrder(
        out_trade_no="DON_OK_1",
        status="pending",
        expire_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    db = _make_db_mock(order)
    payload = DonationNotify(outTradeNo="DON_OK_1", success=True, transactionId="txn2")
    res = asyncio.run(notify_donation(payload, x_token=None, db=db))
    assert res["status"] == "paid"
    assert order.status == "paid"
    db.commit.assert_awaited()
