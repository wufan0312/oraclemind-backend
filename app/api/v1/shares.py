"""分享服务 API —— 按登录用户保存/读取各模块的分享内容。

- 读取：GET /shares?module= 返回当前用户在该模块下已保存的分享（无则返回 null）
- 保存：POST /shares 按 (user_id, module) upsert（已存在则覆盖，实现「重新生成」语义）
- 全部接口需 Bearer token（get_current_user 依赖）

持久化：SQLAlchemy ORM（SQLite / PostgreSQL 通用）。(user_id, module) 唯一由**数据库
唯一约束**保证（缺陷报告 P1-6），写入走 INSERT ... ON CONFLICT DO UPDATE 单语句原子
upsert，替代原先的 select-then-upsert，并发下不会插入重复行也不会丢失更新。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.share import Share
from app.models.user import User
from app.core.audit import audited_commit
from app.schemas.share import ShareCreate, ShareOut

# ON CONFLICT DO UPDATE 是方言专属方法（通用 insert 没有），按当前数据库选取方言 insert
if settings.is_sqlite:
    from sqlalchemy.dialects.sqlite import insert as upsert_insert
else:
    from sqlalchemy.dialects.postgresql import insert as upsert_insert

router = APIRouter(tags=["分享"])


def _to_out(s: Share) -> ShareOut:
    """显式映射 ORM(snake_case) → schema(camelCase)，避免依赖 from_attributes 的字段名匹配。"""
    return ShareOut(
        id=s.id,
        userId=s.user_id,
        module=s.module,
        title=s.title,
        shareText=s.share_text,
        imageUrl=s.image_url,
        imagePrompt=s.image_prompt,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get(
    "/shares",
    response_model=ShareOut | None,
    summary="获取当前用户在某模块的分享（无则返回 null）",
)
async def get_my_share(
    module: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareOut | None:
    """返回当前登录用户指定模块下已保存的分享内容；未保存过返回 null。"""
    res = await db.execute(
        select(Share).where(Share.user_id == user.id, Share.module == module)
    )
    rec = res.scalar_one_or_none()
    return _to_out(rec) if rec else None


@router.post(
    "/shares",
    response_model=ShareOut,
    status_code=status.HTTP_201_CREATED,
    summary="保存/更新分享（按 user+module upsert）",
)
async def upsert_share(
    payload: ShareCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareOut:
    """保存分享内容：同一用户在同模块下已存在则覆盖（实现首次落库 / 重新生成更新）。

    P1-6：单条 ``INSERT ... ON CONFLICT (user_id, module) DO UPDATE`` 由数据库原子完成，
    不再 SELECT 后分支判断；并发请求要么插入、要么更新，不会重复也不会丢更新。
    P1-5：审计行与 upsert 处在同一事务，一次 commit 一起落库。
    """
    stmt = (
        upsert_insert(Share)
        .values(
            user_id=user.id,
            module=payload.module,
            title=payload.title,
            share_text=payload.shareText,
            image_url=payload.imageUrl,
            image_prompt=payload.imagePrompt,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "module"],
            set_={
                "title": payload.title,
                "share_text": payload.shareText,
                "image_url": payload.imageUrl,
                "image_prompt": payload.imagePrompt,
                # ON CONFLICT 分支不走 ORM 的 onupdate，需显式刷新 updated_at
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(stmt)
    # 审计：分享保存（合规 §4.6）—— 与 upsert 同事务
    await audited_commit(db, "share_upsert", "user", user.id, target=payload.module)
    rec = (
        await db.execute(
            select(Share).where(Share.user_id == user.id, Share.module == payload.module)
        )
    ).scalar_one()
    return _to_out(rec)
