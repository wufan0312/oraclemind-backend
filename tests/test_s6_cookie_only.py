"""S6 双凭证 XSS 回归测试：

- 响应体不再返回 ``access_token``（消除「token 出现在响应体、可被 XSS 读取」的暴露面）。
- 认证凭证统一经 httpOnly Cookie（om_auth，SameSite=strict）下发与携带；
  ``_extract_token`` 优先读 Cookie，Bearer 仅作兼容兜底。
- 登录/注册接口在设置 Cookie 的同时，响应体不含任何 token 字段。
"""

import uuid

from fastapi import Request, Response
from fastapi.testclient import TestClient

from app.api.v1 import auth
from app.api.v1.auth import TokenResponse, _extract_token, _set_auth_cookie
from app.main import app


# ===== 工具 =====


def _make_request(headers=None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": headers or [],
        "query_string": b"",
    }
    return Request(scope)


# ===== Schema：响应体无 token 字段 =====


def test_token_response_has_no_token_fields():
    assert "access_token" not in TokenResponse.model_fields
    assert "token_type" not in TokenResponse.model_fields
    assert "user" in TokenResponse.model_fields


# ===== _extract_token：Cookie 优先，Bearer 兜底 =====


def test_extract_token_prefers_cookie_over_bearer():
    req = _make_request(
        [
            (b"cookie", b"om_auth=cookie-val"),
            (b"authorization", b"Bearer header-val"),
        ]
    )
    assert _extract_token(req) == "cookie-val"


def test_extract_token_falls_back_to_bearer():
    req = _make_request([(b"authorization", b"Bearer header-val")])
    assert _extract_token(req) == "header-val"


def test_extract_token_none_when_absent():
    assert _extract_token(_make_request()) is None


# ===== _set_auth_cookie：HttpOnly + SameSite=strict =====


def test_set_auth_cookie_is_httponly_and_strict():
    resp = Response()
    _set_auth_cookie(resp, "tok-123", _make_request())
    sc = resp.headers.get("set-cookie", "")
    assert "om_auth=" in sc
    assert "HttpOnly" in sc
    assert "samesite=strict" in sc.lower()


# ===== 端到端：注册下发 Cookie + 响应体无 token，且 /me 凭 Cookie 可用 =====


def test_register_sets_cookie_and_omits_body_token():
    username = f"s6test_{uuid.uuid4().hex[:12]}"
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "Passw0rd!23", "email": None},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert "access_token" not in body
        assert "token_type" not in body
        assert "user" in body and body["user"]["username"] == username

        sc = r.headers.get("set-cookie", "")
        assert "om_auth=" in sc and "HttpOnly" in sc

        # 注册下发的 Cookie 随后续请求自动携带，/me 可鉴权
        r2 = client.get("/api/v1/auth/me")
        assert r2.status_code == 200, r2.text
        assert r2.json()["username"] == username
