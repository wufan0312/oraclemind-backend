"""支付回调鉴权回归测试（P0 修复：防伪造 success 免费解锁付费权益）。

验证 verify_notify_auth 的四类行为：
- 已配置 secret + 缺失/错误令牌 → 401（不处理订单）
- 已配置 secret + 正确令牌 → None（放行）
- 未配置 secret + 开发环境 → None（放行，本地便利）
- 未配置 secret + 生产环境 → 403（拒绝，防伪造）
"""

import pytest
from fastapi import HTTPException

from app.core import payment_security as ps
from app.core.config import settings


@pytest.fixture
def _restore_settings():
    orig_secret = settings.payment_callback_secret
    orig_env = settings.app_env
    try:
        yield
    finally:
        settings.payment_callback_secret = orig_secret
        settings.app_env = orig_env


def test_configured_missing_token_rejected(_restore_settings):
    settings.payment_callback_secret = "topsecret"
    settings.app_env = "development"
    with pytest.raises(HTTPException) as exc:
        ps.verify_notify_auth(None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        ps.verify_notify_auth("wrong")


def test_configured_valid_token_ok(_restore_settings):
    settings.payment_callback_secret = "topsecret"
    settings.app_env = "development"
    assert ps.verify_notify_auth("topsecret") is None


def test_no_secret_dev_ok(_restore_settings):
    settings.payment_callback_secret = ""
    settings.app_env = "development"
    assert ps.verify_notify_auth(None) is None


def test_no_secret_prod_rejected(_restore_settings):
    settings.payment_callback_secret = ""
    settings.app_env = "production"
    with pytest.raises(HTTPException) as exc:
        ps.verify_notify_auth(None)
    assert exc.value.status_code == 403
