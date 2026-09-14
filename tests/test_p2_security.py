"""后端 P2 安全缺陷回归测试（S5 auth 异常收窄 / S7 XFF 信任门控 / S8 debug 默认 / R7 时区）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.core.config import Settings, settings


# ===== fixtures：还原 settings 改动 =====


@pytest.fixture
def _restore_settings():
    orig_env = settings.app_env
    orig_debug = settings.debug
    orig_proxy = settings.proxy_trusted
    try:
        yield
    finally:
        settings.app_env = orig_env
        settings.debug = orig_debug
        settings.proxy_trusted = orig_proxy


# ===== S5：get_optional_user 不再吞异常，封禁降为匿名 =====


def _make_request_cookie(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [(b"cookie", f"om_auth={token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


def _user_row(user):
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    )
    return db


def test_optional_user_valid_token_returns_user():
    from app.api.v1 import auth
    from app.models.user import User

    user = User(id=10, username="u", is_banned=False)
    token = auth.create_access_token(10, "u")
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=False)):
        got = asyncio.run(auth.get_optional_user(_make_request_cookie(token), _user_row(user)))
    assert got is not None and got.id == 10


def test_optional_user_bad_token_returns_none():
    from app.api.v1 import auth

    req = _make_request_cookie("not-a-valid-token")
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=False)):
        got = asyncio.run(auth.get_optional_user(req, _user_row(None)))
    assert got is None  # 不再抛异常，安全降级为匿名


def test_optional_user_banned_returns_none():
    from app.api.v1 import auth
    from app.models.user import User

    user = User(id=11, username="banned", is_banned=True)
    token = auth.create_access_token(11, "banned")
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=False)):
        got = asyncio.run(auth.get_optional_user(_make_request_cookie(token), _user_row(user)))
    assert got is None  # 与 get_current_user 一致：封禁在可选鉴权端点也生效


def test_optional_user_revoked_token_returns_none():
    from app.api.v1 import auth
    from app.models.user import User

    user = User(id=12, username="rev", is_banned=False)
    token = auth.create_access_token(12, "rev")
    # 已登出（jti 拉黑）→ 视作匿名，不读取身份
    with patch("app.api.v1.auth.is_jwt_blacklisted", new=AsyncMock(return_value=True)):
        got = asyncio.run(auth.get_optional_user(_make_request_cookie(token), _user_row(user)))
    assert got is None


# ===== S7：XFF 仅当 proxy_trusted 才信任 =====


def _req_with_xff(xff: str, client_host: str = "203.0.113.9") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [(b"x-forwarded-for", xff.encode())],
        "query_string": b"",
        "client": ("203.0.113.9", 1234),
    }
    return Request(scope)


def test_client_ip_ignores_xff_when_not_trusted(_restore_settings):
    from app.api.v1 import auth

    settings.proxy_trusted = False
    ip = auth._client_ip(_req_with_xff("1.2.3.4, 5.6.7.8"))
    # 未信任反代：忽略伪造 XFF，使用真实连接 IP
    assert ip == "203.0.113.9"


def test_client_ip_trusts_xff_when_proxy_trusted(_restore_settings):
    from app.api.v1 import auth

    settings.proxy_trusted = True
    ip = auth._client_ip(_req_with_xff("1.2.3.4, 5.6.7.8"))
    # 已信任反代：取 XFF 首段
    assert ip == "1.2.3.4"


# ===== S8：debug 默认 False（源码默认，防止生产漏配时 SQL echo 泄露绑定参数）=====


def test_debug_default_false():
    # 校验 Settings 字段默认值（不依赖 .env 覆盖后的单例），确保新部署未显式配置时安全
    assert Settings.model_fields["debug"].default is False
