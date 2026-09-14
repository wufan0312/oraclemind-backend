"""社区 Pydantic 模型 —— 请求 / 响应（字段 camelCase 与前端对齐）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ============================ 圈子 ============================


class CircleOut(BaseModel):
    """圈子信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    icon: str
    description: str
    sortOrder: int
    postCount: int = 0


# ============================ 公告 ============================


class AnnouncementOut(BaseModel):
    """官方公告。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    pinned: bool
    createdAt: datetime


# ============================ 帖子 ============================


class PostCreate(BaseModel):
    """发帖请求体。"""

    circleSlug: str = Field(..., min_length=1, max_length=32, description="所属圈子 slug")
    title: str = Field(default="", max_length=128, description="标题（可为空）")
    content: str = Field(..., min_length=1, max_length=4000, description="正文")
    images: list[str] = Field(default_factory=list, description="配图 URL 列表")
    topicTags: list[str] = Field(default_factory=list, description="话题标签列表")


class PostOut(BaseModel):
    """帖子详情（列表/详情通用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    authorId: int | None
    authorName: str
    circleSlug: str
    circleName: str = ""
    circleIcon: str = "🔮"
    title: str
    content: str
    images: list[str] = Field(default_factory=list)
    topicTags: list[str] = Field(default_factory=list)
    likeCount: int
    commentCount: int
    viewCount: int
    isPinned: bool
    createdAt: datetime
    likeByMe: bool = False  # 当前登录用户是否已赞（未登录为 False）


# ============================ 评论 ============================


class CommentCreate(BaseModel):
    """发评论请求体。"""

    content: str = Field(..., min_length=1, max_length=1000, description="评论正文")
    parentId: int | None = Field(default=None, description="父评论ID（楼中楼）")


class CommentOut(BaseModel):
    """评论详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    postId: int
    authorId: int | None
    authorName: str
    parentId: int | None
    content: str
    likeCount: int
    createdAt: datetime
    likeByMe: bool = False


# ============================ 点赞 ============================


class LikeToggle(BaseModel):
    """点赞 toggle 请求体。"""

    targetType: str = Field(..., pattern="^(post|comment)$", description="对象类型")
    targetId: int = Field(..., gt=0, description="对象ID")


class LikeToggleResult(BaseModel):
    """点赞 toggle 返回。"""

    liked: bool
    likeCount: int


# ============================ 排行 ============================


class HotPostItem(BaseModel):
    """热门帖子榜单项。"""

    id: int
    title: str
    authorName: str
    circleName: str
    likeCount: int
    commentCount: int
    createdAt: datetime


class TopUserItem(BaseModel):
    """达人榜单项。"""

    userId: int
    username: str
    postCount: int
    likeTotal: int


class RankOut(BaseModel):
    """社区排行（热门帖子 + 达人）。"""

    hotPosts: list[HotPostItem] = Field(default_factory=list)
    topUsers: list[TopUserItem] = Field(default_factory=list)


# 复用：帖子详情（含评论）组合响应
class PostDetailOut(PostOut):
    """帖子详情（含评论列表）。"""

    comments: list[CommentOut] = Field(default_factory=list)
