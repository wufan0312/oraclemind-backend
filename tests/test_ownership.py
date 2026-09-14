"""身份归属公共封装单元测试（抽取自 stash/donations/premium/reports 的重复样板）。

覆盖：
- ``require_identity``：匿名且无 visitorId → 400；登录或带 visitorId → 放行。
- ``actor_id_of``：登录返回 user.id；匿名返回 visitorId 或兜底 "anonymous"。
- ``resolve_owner_key``：登录 ``user:{id}``；匿名 ``visitor:{vid}``；无身份 ``None``。

这些函数被多处路由复用，行为必须与原有内联实现完全一致，避免回归。
"""

import pytest
from fastapi import HTTPException

from app.core.ownership import actor_id_of, require_identity, resolve_owner_key
from app.models.user import User


def _user(uid: int = 5) -> User:
    return User(id=uid)


# ===== require_identity =====


def test_require_identity_logged_in_passes():
    # 已登录：无论 visitor_id 如何都放行
    require_identity(_user(), None)
    require_identity(_user(), "abc")


def test_require_identity_anon_with_visitor_passes():
    require_identity(None, "visitor-abc")


def test_require_identity_anon_without_visitor_raises():
    with pytest.raises(HTTPException) as exc:
        require_identity(None, None)
    assert exc.value.status_code == 400
    # 默认文案保持一致
    assert "visitorId" in exc.value.detail


def test_require_identity_custom_detail():
    with pytest.raises(HTTPException) as exc:
        require_identity(None, "", detail="自定义提示")
    assert exc.value.detail == "自定义提示"


# ===== actor_id_of =====


def test_actor_id_logged_in():
    assert actor_id_of(_user(42)) == "42"


def test_actor_id_anon_with_visitor():
    assert actor_id_of(None, "visitor-abc") == "visitor-abc"


def test_actor_id_anon_without_visitor_defaults_anonymous():
    assert actor_id_of(None, None) == "anonymous"
    assert actor_id_of(None, "") == "anonymous"


# ===== resolve_owner_key =====


def test_resolve_owner_key_logged_in():
    assert resolve_owner_key(_user(7), None) == "user:7"
    assert resolve_owner_key(_user(7), "ignored") == "user:7"


def test_resolve_owner_key_anon_with_visitor():
    assert resolve_owner_key(None, "visitor-abc") == "visitor:visitor-abc"


def test_resolve_owner_key_no_identity():
    assert resolve_owner_key(None, None) is None
    assert resolve_owner_key(None, "") is None
