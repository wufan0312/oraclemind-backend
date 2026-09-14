"""身份归属公共封装（抽取自 stash / donations / premium / reports 路由的重复样板）。

本模块集中后端「匿名/登录身份」相关的可复用逻辑，避免各路由重复实现导致逻辑漂移
（尤其是安全敏感的身份守卫与审计 actor 归一化）：

- ``require_identity``：未登录且未带 visitorId 时拒绝请求（约 5 处重复守卫，已统一）。
- ``actor_id_of``：审计 actor_id 归一化（``user:{id}`` / ``visitor:<id>`` / ``anonymous``，
  约 6 处重复拼串，已统一）。
- ``resolve_owner_key``：构造上云 KV 的身份键（``user:{id}`` / ``visitor:{vid}`` / None），
  原 stash 私有 ``_owner_key`` 上提，便于其他需要 owner_key 的模块复用。

仅抽取纯逻辑，不改变任何路由的签名与鉴权依赖（``get_optional_user`` / ``get_visitor_id``
仍由各端点显式声明），以最小改动面消除重复、降低回归风险。
"""

from fastapi import HTTPException, status

from app.models.user import User


def require_identity(
    user: User | None,
    visitor_id: str | None,
    *,
    detail: str = "未登录时必须提供 visitorId",
) -> None:
    """身份守卫：登录态或持有合法 visitorId 才放行，否则 400。

    消除各路由重复的「未登录必须提供 visitorId」判断（stash put/delete、
    donations/premium 下单、premium entitlements、reports 创建）。

    - 已登录（``user`` 非 None）：放行；
    - 匿名但带 ``visitor_id``：放行；
    - 匿名且无 ``visitor_id``：拒绝。
    """
    if user is None and not visitor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def actor_id_of(user: User | None, visitor_id: str | None = None) -> str:
    """审计 actor_id 归一化。

    登录态返回 ``str(user.id)``；匿名态返回 ``visitor_id`` 或兜底 ``"anonymous"``。
    消除各路由重复的 ``str(user.id) if user is not None else (visitor_id or "anonymous")`` 拼串。
    """
    if user is not None:
        return str(user.id)
    return visitor_id or "anonymous"


def resolve_owner_key(user: User | None, visitor_id: str | None) -> str | None:
    """构造上云 KV 的身份键；匿名且无 visitorId 时返回 None（无法隔离，调用方应拒绝）。

    - 登录态：``user:{user.id}``
    - 匿名态：``visitor:{visitor_id}``
    - 无身份：``None``

    原 stash 私有 ``_owner_key`` 上提至此，供需要 owner_key 的模块复用。
    """
    if user is not None:
        return f"user:{user.id}"
    if visitor_id:
        return f"visitor:{visitor_id}"
    return None
