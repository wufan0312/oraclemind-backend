"""用户资料路由 —— 获取 / 更新当前登录用户的出生信息与偏好。

- 必须携带 Bearer token（鉴权复用 auth.get_current_user）
- 资料为独立 user_profiles 表，与 users 一对一
"""

from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.crypto import decrypt_value, encrypt_value
from app.db.session import get_db
from app.models.user import User
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/user", tags=["user-profile"])


# ===== Pydantic Schemas =====


class BirthInfo(BaseModel):
    """出生信息（与前端 VisitorBirth 对齐）。"""

    date: str | None = Field(default=None, description="公历出生日期 YYYY-MM-DD")
    time: str | None = Field(default=None, description="时辰名：子时~亥时 / 不详")
    gender: str | None = Field(default=None, description="性别：男 / 女")
    lunarYear: int | None = Field(default=None, description="农历出生年")
    lunarMonth: int | None = Field(default=None, description="农历出生月（闰月用负数）")
    lunarDay: int | None = Field(default=None, description="农历出生日")
    province: str | None = Field(default=None, description="出生省份")
    city: str | None = Field(default=None, description="出生城市")
    lat: float | None = Field(default=None, description="出生地纬度")
    lng: float | None = Field(default=None, description="出生地经度")


class UserProfileResponse(BaseModel):
    """用户资料响应。"""

    userId: int
    username: str
    email: str | None = None
    birth: BirthInfo | None = None
    timezone: str | None = None
    theme: str | None = None
    notes: str | None = None
    updatedAt: int | None = None


class UserProfileUpdate(BaseModel):
    """更新用户资料请求（所有字段可选，只传需要修改的字段）。"""

    birth: BirthInfo | None = Field(default=None, description="出生信息")
    timezone: str | None = Field(default=None, max_length=32)
    theme: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None)


class MigrateVisitorRequest(BaseModel):
    """访客数据迁移请求（登录时将 localStorage 中的出生信息同步到后端）。"""

    birth: BirthInfo


# ===== Helpers =====


def _profile_to_response(user: User, profile: UserProfile | None) -> UserProfileResponse:
    """将 User + UserProfile ORM 对象转为 API 响应。"""
    birth = None
    if profile and profile.birth:
        # 解密（旧明文无 enc:: 前缀时原样返回），再解析为 dict
        plain = decrypt_value(profile.birth)
        try:
            raw = json.loads(plain) if isinstance(plain, str) else (plain or {})
        except (json.JSONDecodeError, TypeError):
            raw = {}
        if isinstance(raw, dict):
            # 仅取 BirthInfo 声明的字段，避免脏数据（如遗留额外键）导致校验失败
            fields = BirthInfo.model_fields.keys()
            data = {k: raw.get(k) for k in fields}
            if data.get("date"):
                birth = BirthInfo(**data)
    return UserProfileResponse(
        userId=user.id,
        username=user.username,
        email=user.email,
        birth=birth,
        timezone=profile.timezone if profile else None,
        theme=profile.theme if profile else None,
        notes=profile.notes if profile else None,
        updatedAt=int(profile.updated_at.timestamp() * 1000) if profile and profile.updated_at else None,
    )


async def _get_or_create_profile(db: AsyncSession, user_id: int) -> UserProfile:
    """获取或创建用户资料（懒创建）。"""
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile:
        return profile
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


def _apply_birth(profile: UserProfile, birth: BirthInfo) -> None:
    """将 BirthInfo 聚合加密写入 UserProfile.birth（原地修改，不提交）。

    对应缺陷报告 P0-4：明文 JSON 经 encrypt_value 转为 ``enc::<token>`` 密文落库。
    """
    profile.birth = encrypt_value(birth.model_dump())


# ===== Routes =====


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前登录用户的资料（含出生信息）。"""
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return _profile_to_response(user, profile)


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    req: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前登录用户的资料（出生信息 / 偏好设置）。"""
    profile = await _get_or_create_profile(db, user.id)

    if req.birth is not None:
        _apply_birth(profile, req.birth)
    if req.timezone is not None:
        profile.timezone = req.timezone
    if req.theme is not None:
        profile.theme = req.theme
    if req.notes is not None:
        profile.notes = req.notes

    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _profile_to_response(user, profile)


@router.post("/profile/migrate", response_model=UserProfileResponse)
async def migrate_visitor(
    req: MigrateVisitorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """登录时将访客 localStorage 中的出生信息迁移到后端。

    仅当后端尚未存储出生信息时才覆盖（避免登录后覆盖已设置的数据）。
    """
    profile = await _get_or_create_profile(db, user.id)

    # 仅当后端无出生信息时才迁移
    if not profile.birth:
        _apply_birth(profile, req.birth)
        profile.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(profile)

    return _profile_to_response(user, profile)


@router.delete("/profile/birth", response_model=UserProfileResponse)
async def clear_birth(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清除当前登录用户的出生信息（保留其他偏好设置）。"""
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.birth = None
    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _profile_to_response(user, profile)
