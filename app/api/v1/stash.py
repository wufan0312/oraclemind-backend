"""前端业务数据上云 KV 接口（缺陷报告 P1-8）。

- GET    /api/v1/stash            拉取当前身份全部上云数据 {key: jsonString}
- PUT    /api/v1/stash            写入/覆盖一条（按 (owner_key, key) 原子 upsert）
- DELETE /api/v1/stash/{key}      删除一条

身份：登录态用 ``user:{id}``；匿名态用 ``visitor:{visitor_id}``（必须带 visitorId 查询参数）。

**出生信息不在本接口的同步范围内**：``om_visitor_birth`` / ``om_user_birth*`` 走
``/api/v1/user/profile``（P0-4 已做字段级加密），上云等于把明文出生信息塞回 DB。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_optional_user, get_visitor_id
from app.core.config import settings
from app.core.ownership import require_identity, resolve_owner_key
from app.db.session import get_db
from app.models.user import User
from app.models.user_stash import UserStash

if settings.is_sqlite:
    from sqlalchemy.dialects.sqlite import insert as upsert_insert
else:
    from sqlalchemy.dialects.postgresql import insert as upsert_insert

router = APIRouter(tags=["上云存储"])


class StashSetRequest(BaseModel):
    """写入一条上云数据；value 为前端 JSON.stringify 后的字符串。

    Q2 加固：单条 value 上限 1MB（见下方 max_length）；单身份总键数 / 总体积上限由
    ``settings.stash_max_keys`` / ``settings.stash_max_bytes`` 在服务端强制（put_stash 守卫），
    防止单个匿名/登录身份无限堆积撑爆存储。
    """

    key: str = Field(min_length=1, max_length=128)
    value: str = Field(max_length=1_000_000, description="JSON 序列化的业务数据（单条 ≤1MB）")


@router.get("/stash", response_model=dict[str, str], summary="拉取当前身份全部上云数据")
async def list_stash(
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    owner = resolve_owner_key(user, visitorId)
    if owner is None:
        return {}
    rows = (
        await db.execute(select(UserStash).where(UserStash.owner_key == owner))
    ).scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/stash", status_code=status.HTTP_204_NO_CONTENT, summary="写入/覆盖一条上云数据")
async def put_stash(
    payload: StashSetRequest,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    require_identity(user, visitorId)
    owner = resolve_owner_key(user, visitorId)
    # Q2 守卫：单身份键数 / 总体积上限（防无限堆积撑爆存储）。
    # 先统计当前身份已有键数与 value 总字节，再判断是否超出 settings 阈值。
    stat = (
        await db.execute(
            select(
                func.count(UserStash.id),
                func.coalesce(func.sum(func.length(UserStash.value)), 0),
            ).where(UserStash.owner_key == owner)
        )
    ).one()
    existing_count, existing_bytes = int(stat[0]), int(stat[1] or 0)
    key_exists = (
        await db.execute(
            select(UserStash.id).where(
                UserStash.owner_key == owner, UserStash.key == payload.key
            )
        )
    ).scalar_one_or_none() is not None
    new_bytes = len(payload.value.encode("utf-8"))
    if not key_exists and existing_count >= settings.stash_max_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"上云数据键数已达上限（{settings.stash_max_keys}）",
        )
    if existing_bytes + new_bytes > settings.stash_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上云数据总体积超限",
        )
    stmt = (
        upsert_insert(UserStash)
        .values(owner_key=owner, key=payload.key, value=payload.value)
        .on_conflict_do_update(
            index_elements=["owner_key", "key"],
            set_={"value": payload.value, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.commit()


@router.delete(
    "/stash/{key}", status_code=status.HTTP_204_NO_CONTENT, summary="删除一条上云数据"
)
async def delete_stash(
    key: str,
    user: User | None = Depends(get_optional_user),
    visitorId: str | None = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    require_identity(user, visitorId)
    owner = resolve_owner_key(user, visitorId)
    await db.execute(
        delete(UserStash).where(UserStash.owner_key == owner, UserStash.key == key)
    )
    await db.commit()
