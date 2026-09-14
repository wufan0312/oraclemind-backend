"""后端 P1 缺陷修复回归测试（S2 封禁 / S3 Cookie Secure / S4 弱密钥 / S5 解密异常 / S6 排盘异步 / S7 全局异常）。

S8（报告搜索内存）因依赖 DB 数据，放在重启后 smoke test 验证，此处不做重 DB 用例。
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response

from app.core import crypto
from app.core.config import settings
from app.core.paipan_cache import cached_paipan
from app.main import app


# ===== fixtures =====


@pytest.fixture
def _restore_crypto():
    orig_key = settings.encryption_key
    orig_jwt = settings.jwt_secret
    orig_env = settings.app_env
    orig_fernet = crypto._fernet
    try:
        yield
    finally:
        settings.encryption_key = orig_key
        settings.jwt_secret = orig_jwt
        settings.app_env = orig_env
        crypto._fernet = orig_fernet


@pytest.fixture
def _restore_settings():
    orig_env = settings.app_env
    try:
        yield
    finally:
        settings.app_env = orig_env


# ===== S2 封禁用户未拦截 =====


def _make_request(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [(b"cookie", f"om_auth={token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


def test_banned_user_rejected():
    from app.api.v1 import auth
    from app.models.user import User

    user = User(id=1, username="banned", is_banned=True)
    token = auth.create_access_token(1, "banned")
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    )
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=False)):
        with pytest.raises(Exception) as exc:
            asyncio.run(auth.get_current_user(_make_request(token), db))
    # 期望 403；HTTPException.status_code 在 .value 上（pytest.raises 包裹）
    assert exc.value.status_code == 403


def test_normal_user_ok():
    from app.api.v1 import auth
    from app.models.user import User

    user = User(id=2, username="ok", is_banned=False)
    token = auth.create_access_token(2, "ok")
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    )
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=False)):
        got = asyncio.run(auth.get_current_user(_make_request(token), db))
    assert got.id == 2


# ===== S3 Cookie Secure（生产强制） =====


def test_cookie_secure_in_production(_restore_settings):
    from app.api.v1 import auth

    settings.app_env = "production"
    resp = Response()
    auth._set_auth_cookie(resp, "tok", _make_request("x"))
    assert "secure" in resp.headers.get("set-cookie", "").lower()


def test_cookie_not_secure_in_dev(_restore_settings):
    from app.api.v1 import auth

    settings.app_env = "development"
    resp = Response()
    auth._set_auth_cookie(resp, "tok", _make_request("x"))
    assert "secure" not in resp.headers.get("set-cookie", "").lower()


# ===== S4 弱加密密钥回退 =====


def test_prod_requires_encryption_key(_restore_crypto):
    settings.encryption_key = ""
    settings.app_env = "production"
    with pytest.raises(RuntimeError):
        crypto._build_fernet()


def test_dev_fallback_to_jwt(_restore_crypto):
    settings.encryption_key = ""
    settings.app_env = "development"
    settings.jwt_secret = "dev-jwt-secret"
    f = crypto._build_fernet()  # 不应抛错（dev 回退）
    assert f is not None


# ===== S5 解密异常吞噬 =====


def test_decrypt_invalid_token_returns_original(_restore_crypto):
    settings.encryption_key = "keyA"
    fa = crypto._build_fernet()
    enc = crypto.PREFIX + fa.encrypt(b"secret").decode()
    # 切换到不同密钥，使其解密失败（InvalidToken）
    settings.encryption_key = "keyB"
    crypto._fernet = crypto._build_fernet()
    assert crypto.decrypt_value(enc) == enc  # 返回原文占位，不抛、不静默成别的值


def test_decrypt_other_error_propagates(_restore_crypto):
    settings.encryption_key = "keyA"
    crypto._fernet = crypto._build_fernet()

    class _Bad:
        def decrypt(self, token):
            raise ValueError("corrupt")

    crypto._fernet = _Bad()
    # 非 InvalidToken 的异常必须向上传播（不再被吞）
    with pytest.raises(ValueError):
        crypto.decrypt_value(crypto.PREFIX + "sometoken")


# ===== S6 排盘计算移出事件循环 + 缓存 =====


def test_cached_paipan_threaded_and_cached():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"r": 1}

    res, hit = asyncio.run(cached_paipan("ns", {"a": 1}, compute))
    assert res == {"r": 1} and hit is False
    res2, hit2 = asyncio.run(cached_paipan("ns", {"a": 1}, compute))
    assert hit2 is True and calls["n"] == 1  # 命中缓存，compute 未重跑


# ===== S7 全局异常处理器 =====


def test_global_exception_handler_returns_500_json():
    handler = app.exception_handlers[Exception]
    scope = {"type": "http", "method": "GET", "path": "/boom", "headers": []}
    req = Request(scope)
    resp = asyncio.run(handler(req, RuntimeError("x")))
    assert resp.status_code == 500
    body = json.loads(resp.body)
    assert body["detail"] == "服务器内部错误，请稍后重试。"
