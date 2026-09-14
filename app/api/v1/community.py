"""社区综合服务 API —— 圈子 / 动态流 / 评论 / 点赞 / 公告 / 排行。

- 只读接口（circles / announcements / posts 列表 / 帖子详情 / rank）**公开**，无需登录；
  登录用户会额外标记 likeByMe（当前是否已赞）。
- 写操作（发帖 / 评论 / 点赞）需登录（get_current_user，httpOnly Cookie 自动携带）。

数据层：SQLAlchemy ORM（SQLite / PostgreSQL 通用）。JSON 数组字段以 Text 存储，
读写经 json.loads / json.dumps。
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user, get_optional_user
from app.core.audit import audited_commit
from app.db.session import get_db
from app.models.community import (
    CommunityAnnouncement,
    CommunityCircle,
    CommunityComment,
    CommunityLike,
    CommunityPost,
)
from app.models.user import User
from app.schemas.community import (
    AnnouncementOut,
    CircleOut,
    CommentCreate,
    CommentOut,
    LikeToggle,
    LikeToggleResult,
    PostCreate,
    PostDetailOut,
    PostOut,
    RankOut,
    HotPostItem,
    TopUserItem,
)

router = APIRouter(tags=["社区"])


# ============================ 内部工具 ============================


def _load_json(text: str | None, default: list) -> list:
    """Text(JSON) -> list，解析失败回退默认。"""
    if not text:
        return list(default)
    try:
        v = json.loads(text)
        return v if isinstance(v, list) else list(default)
    except (json.JSONDecodeError, TypeError):
        return list(default)


async def _circle_map(db: AsyncSession) -> dict[str, CommunityCircle]:
    rows = (await db.execute(select(CommunityCircle))).scalars().all()
    return {c.slug: c for c in rows}


async def _liked_post_ids(db: AsyncSession, user: User | None, post_ids: list[int]) -> set[int]:
    if not user or not post_ids:
        return set()
    res = await db.execute(
        select(CommunityLike.target_id).where(
            CommunityLike.user_id == user.id,
            CommunityLike.target_type == "post",
            CommunityLike.target_id.in_(post_ids),
        )
    )
    return set(res.scalars().all())


def _post_out(
    p: CommunityPost,
    circles: dict[str, CommunityCircle],
    liked: bool = False,
) -> PostOut:
    c = circles.get(p.circle_slug)
    return PostOut(
        id=p.id,
        authorId=p.author_id,
        authorName=p.author_name,
        circleSlug=p.circle_slug,
        circleName=c.name if c else p.circle_slug,
        circleIcon=c.icon if c else "🔮",
        title=p.title,
        content=p.content,
        images=_load_json(p.images, []),
        topicTags=_load_json(p.topic_tags, []),
        likeCount=p.like_count,
        commentCount=p.comment_count,
        viewCount=p.view_count,
        isPinned=p.is_pinned,
        createdAt=p.created_at,
        likeByMe=liked,
    )


def _comment_out(c: CommunityComment, liked: bool = False) -> CommentOut:
    return CommentOut(
        id=c.id,
        postId=c.post_id,
        authorId=c.author_id,
        authorName=c.author_name,
        parentId=c.parent_id,
        content=c.content,
        likeCount=c.like_count,
        createdAt=c.created_at,
        likeByMe=liked,
    )


# ============================ 圈子 ============================


@router.get("/community/circles", response_model=list[CircleOut], summary="圈子列表")
async def list_circles(db: AsyncSession = Depends(get_db)) -> list[CircleOut]:
    circles = (
        await db.execute(select(CommunityCircle).order_by(CommunityCircle.sort_order))
    ).scalars().all()
    counts = (
        await db.execute(
            select(CommunityPost.circle_slug, func.count())
            .where(CommunityPost.status == "published")
            .group_by(CommunityPost.circle_slug)
        )
    ).all()
    count_map = {slug: n for slug, n in counts}
    return [
        CircleOut(
            id=c.id,
            slug=c.slug,
            name=c.name,
            icon=c.icon,
            description=c.description,
            sortOrder=c.sort_order,
            postCount=count_map.get(c.slug, 0),
        )
        for c in circles
    ]


# ============================ 公告 ============================


@router.get(
    "/community/announcements",
    response_model=list[AnnouncementOut],
    summary="公告列表（置顶优先）",
)
async def list_announcements(db: AsyncSession = Depends(get_db)) -> list[AnnouncementOut]:
    anns = (
        await db.execute(
            select(CommunityAnnouncement).order_by(
                CommunityAnnouncement.pinned.desc(),
                CommunityAnnouncement.created_at.desc(),
            )
        )
    ).scalars().all()
    return [AnnouncementOut.model_validate(a) for a in anns]


# ============================ 帖子流 ============================


@router.get("/community/posts", summary="帖子流（公开，支持过滤/排序/搜索/分页）")
async def list_posts(
    circle: str | None = Query(default=None, description="圈子 slug 过滤"),
    sort: str = Query(default="latest", pattern="^(latest|hot)$", description="latest/hot"),
    q: str | None = Query(default=None, description="关键词（标题/正文/标签）"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict[str, Any]:
    stmt = select(CommunityPost).where(CommunityPost.status == "published")
    if circle:
        stmt = stmt.where(CommunityPost.circle_slug == circle)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CommunityPost.title.ilike(like),
                CommunityPost.content.ilike(like),
                CommunityPost.topic_tags.ilike(like),
            )
        )
    total = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = total.scalar_one()

    if sort == "hot":
        stmt = stmt.order_by(
            CommunityPost.is_pinned.desc(),
            CommunityPost.like_count.desc(),
            CommunityPost.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(
            CommunityPost.is_pinned.desc(),
            CommunityPost.created_at.desc(),
        )

    rows = (
        await db.execute(stmt.limit(pageSize).offset((page - 1) * pageSize))
    ).scalars().all()

    circles = await _circle_map(db)
    liked_set = await _liked_post_ids(db, user, [p.id for p in rows])
    items = [_post_out(p, circles, liked=(p.id in liked_set)) for p in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "hasMore": page * pageSize < total,
    }


# ============================ 帖子详情 ============================


@router.get(
    "/community/posts/{post_id}",
    response_model=PostDetailOut,
    summary="帖子详情（含评论，浏览数+1）",
)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PostDetailOut:
    post = (
        await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    ).scalar_one_or_none()
    if post is None or post.status != "published":
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    # 浏览数 +1（轻量，直接提交）
    post.view_count = (post.view_count or 0) + 1
    await db.commit()

    circles = await _circle_map(db)
    liked_set = await _liked_post_ids(db, user, [post.id])
    out = _post_out(post, circles, liked=(post.id in liked_set))

    comments = (
        await db.execute(
            select(CommunityComment)
            .where(CommunityComment.post_id == post_id)
            .order_by(CommunityComment.created_at.asc())
        )
    ).scalars().all()

    comment_liked: set[int] = set()
    if user and comments:
        res = await db.execute(
            select(CommunityLike.target_id).where(
                CommunityLike.user_id == user.id,
                CommunityLike.target_type == "comment",
                CommunityLike.target_id.in_([c.id for c in comments]),
            )
        )
        comment_liked = set(res.scalars().all())

    out.comments = [_comment_out(c, liked=(c.id in comment_liked)) for c in comments]
    return out


# ============================ 发帖 ============================


@router.post(
    "/community/posts",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    summary="发帖（需登录）",
)
async def create_post(
    payload: PostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostOut:
    # 圈子必须存在
    circle = (
        await db.execute(
            select(CommunityCircle).where(CommunityCircle.slug == payload.circleSlug)
        )
    ).scalar_one_or_none()
    if circle is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="圈子不存在")

    post = CommunityPost(
        author_id=user.id,
        author_name=user.username,
        circle_slug=payload.circleSlug,
        title=payload.title or "",
        content=payload.content,
        images=json.dumps(payload.images, ensure_ascii=False),
        topic_tags=json.dumps(payload.topicTags, ensure_ascii=False),
        like_count=0,
        comment_count=0,
        view_count=0,
        is_pinned=False,
        status="published",
    )
    db.add(post)
    await audited_commit(db, "community_post_create", "post", 0, target=payload.circleSlug)
    circles = await _circle_map(db)
    return _post_out(post, circles)


# ============================ 评论 ============================


@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="评论 / 楼中楼（需登录）",
)
async def add_comment(
    post_id: int,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentOut:
    post = (
        await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    ).scalar_one_or_none()
    if post is None or post.status != "published":
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    # parent 存在性校验
    if payload.parentId is not None:
        parent = (
            await db.execute(
                select(CommunityComment).where(CommunityComment.id == payload.parentId)
            )
        ).scalar_one_or_none()
        if parent is None or parent.post_id != post_id:
            from fastapi import HTTPException

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父评论不存在")

    comment = CommunityComment(
        post_id=post_id,
        author_id=user.id,
        author_name=user.username,
        parent_id=payload.parentId,
        content=payload.content,
        like_count=0,
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    await audited_commit(db, "community_comment_create", "post", post_id)
    return _comment_out(comment)


# ============================ 点赞 toggle ============================


@router.post(
    "/community/likes/toggle",
    response_model=LikeToggleResult,
    summary="点赞 / 取消点赞（需登录，幂等）",
)
async def toggle_like(
    payload: LikeToggle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResult:
    # 目标存在性校验
    if payload.targetType == "post":
        target = (
            await db.execute(select(CommunityPost).where(CommunityPost.id == payload.targetId))
        ).scalar_one_or_none()
        if target is None or target.status != "published":
            from fastapi import HTTPException

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        count_field = "like_count"
    else:
        target = (
            await db.execute(
                select(CommunityComment).where(CommunityComment.id == payload.targetId)
            )
        ).scalar_one_or_none()
        if target is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")
        count_field = "like_count"

    existing = (
        await db.execute(
            select(CommunityLike).where(
                CommunityLike.user_id == user.id,
                CommunityLike.target_type == payload.targetType,
                CommunityLike.target_id == payload.targetId,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        await db.delete(existing)
        setattr(target, count_field, max(0, (getattr(target, count_field) or 0) - 1))
        liked = False
    else:
        db.add(
            CommunityLike(
                user_id=user.id,
                target_type=payload.targetType,
                target_id=payload.targetId,
            )
        )
        setattr(target, count_field, (getattr(target, count_field) or 0) + 1)
        liked = True

    await audited_commit(db, "community_like_toggle", payload.targetType, payload.targetId)
    return LikeToggleResult(liked=liked, likeCount=getattr(target, count_field))


# ============================ 排行 ============================


@router.get("/community/rank", response_model=RankOut, summary="社区排行（热门帖子 + 达人榜）")
async def community_rank(db: AsyncSession = Depends(get_db)) -> RankOut:
    circles = await _circle_map(db)

    # 热门帖子：按点赞数取前 8
    hot = (
        await db.execute(
            select(CommunityPost)
            .where(CommunityPost.status == "published")
            .order_by(CommunityPost.like_count.desc(), CommunityPost.created_at.desc())
            .limit(8)
        )
    ).scalars().all()
    hot_posts = [
        HotPostItem(
            id=p.id,
            title=p.title or p.content[:20],
            authorName=p.author_name,
            circleName=circles.get(p.circle_slug).name if circles.get(p.circle_slug) else p.circle_slug,
            likeCount=p.like_count,
            commentCount=p.comment_count,
            createdAt=p.created_at,
        )
        for p in hot
    ]

    # 达人榜：按 author_id（非空）聚合 发帖数 + 获赞总数，关联 users 取 username
    rows = (
        await db.execute(
            select(
                CommunityPost.author_id,
                func.count(CommunityPost.id),
                func.coalesce(func.sum(CommunityPost.like_count), 0),
            )
            .where(CommunityPost.author_id.isnot(None), CommunityPost.status == "published")
            .group_by(CommunityPost.author_id)
            .order_by(func.sum(CommunityPost.like_count).desc(), func.count(CommunityPost.id).desc())
            .limit(8)
        )
    ).all()
    user_ids = [r[0] for r in rows]
    users = {}
    if user_ids:
        urows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u.username for u in urows}
    top_users = [
        TopUserItem(
            userId=r[0],
            username=users.get(r[0], "同修"),
            postCount=r[1],
            likeTotal=int(r[2]),
        )
        for r in rows
    ]

    return RankOut(hotPosts=hot_posts, topUsers=top_users)
