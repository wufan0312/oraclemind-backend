"""社区域 ORM 模型 —— 圈子 / 帖子 / 评论 / 点赞 / 公告。

综合社区页面（/community）背后的数据层：
- community_circles：话题圈子（八字 / 塔罗 / 姓名 / 疗愈 / 解梦 / 风水 …）
- community_posts：帖子（作者可空，空=官方/匿名；author_name 冗余存储展示名）
- community_comments：评论（parent_id 支持楼中楼）
- community_likes：点赞记录（user_id + target_type + target_id 唯一，幂等 toggle）
- community_announcements：官方公告 / 活动

与全站一致：开发 SQLite、生产 PostgreSQL（仅改 DATABASE_URL）；主键用
BigInteger().with_variant(Integer, 'sqlite') 兼容双库；时间戳 server_default=func.now()。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# JSON 数组以 Text 存储（SQLite / PG 通用），读写时 json.loads / json.dumps。
# 避免直接用 PG 专属 JSON 类型，保持双库一致。


class CommunityCircle(Base):
    """话题圈子（如八字、塔罗、姓名、疗愈）。"""

    __tablename__ = "community_circles"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    slug: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, comment="圈子标识：bazi / tarot / name …"
    )
    name: Mapped[str] = mapped_column(String(32), comment="展示名")
    icon: Mapped[str] = mapped_column(String(16), default="🔮", comment="emoji 图标")
    description: Mapped[str] = mapped_column(String(128), default="", comment="一句话简介")
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序权重（小在前）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CommunityPost(Base):
    """社区帖子（动态流主体）。"""

    __tablename__ = "community_posts"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    author_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="作者用户ID（FK users.id）；空=官方/匿名"
    )
    author_name: Mapped[str] = mapped_column(
        String(64), default="匿名", comment="冗余展示名（登录时取 username）"
    )
    circle_slug: Mapped[str] = mapped_column(
        String(32), index=True, comment="所属圈子 slug"
    )
    title: Mapped[str] = mapped_column(String(128), default="", comment="标题（可空）")
    content: Mapped[str] = mapped_column(Text, comment="正文")
    images: Mapped[str] = mapped_column(
        Text, default="[]", comment="配图 URL 数组（JSON 字符串）"
    )
    topic_tags: Mapped[str] = mapped_column(
        Text, default="[]", comment="话题标签数组（JSON 字符串）"
    )
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, comment="评论数")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览数")
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否置顶（官方公告类帖子）"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="published", comment="published / hidden"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommunityComment(Base):
    """评论（parent_id 支持楼中楼）。"""

    __tablename__ = "community_comments"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    post_id: Mapped[int] = mapped_column(
        Integer, index=True, comment="所属帖子ID（FK community_posts.id）"
    )
    author_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="作者用户ID；空=匿名"
    )
    author_name: Mapped[str] = mapped_column(String(64), default="匿名", comment="冗余展示名")
    parent_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="父评论ID（楼中楼）"
    )
    content: Mapped[str] = mapped_column(Text, comment="评论正文")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class CommunityLike(Base):
    """点赞记录（幂等 toggle 依赖此表去重）。"""

    __tablename__ = "community_likes"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_community_likes_user_target"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, index=True, comment="点赞用户ID（FK users.id，必需登录）"
    )
    target_type: Mapped[str] = mapped_column(
        String(16), index=True, comment="点赞对象类型：post / comment"
    )
    target_id: Mapped[int] = mapped_column(Integer, index=True, comment="对象ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CommunityAnnouncement(Base):
    """官方公告 / 活动。"""

    __tablename__ = "community_announcements"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String(128), comment="公告标题")
    content: Mapped[str] = mapped_column(Text, comment="公告正文")
    author_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="发布者用户ID；空=系统"
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否置顶"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
