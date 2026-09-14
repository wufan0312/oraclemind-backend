"""认证路由 —— 注册 / 登录 / 登出 / 获取当前用户。

- 密码哈希：passlib pbkdf2_sha256（纯 Python，免 C 编译）
- Token：pyjwt HS256，7 天有效期，携带 jti 用于登出拉黑
- 鉴权：httpOnly Cookie（om_auth）优先；Authorization: Bearer 仅作兼容兜底
- 限流：登录/注册按 IP 固定窗口限流（Redis 共享，降级到内存）
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.validators import is_valid_visitor_id
from app.core.redis_service import (
    acquire_visitor_lock,
    blacklist_jwt,
    is_jwt_blacklisted,
    rate_limit_hit,
    release_visitor_lock,
)
from app.db.session import get_db
from app.models.user import User
from app.core.audit import audited_commit
from app.services.migration import migrate_visitor_reports

router = APIRouter(tags=["auth"])

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ===== Pydantic Schemas =====


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    visitorId: str | None = Field(default=None, max_length=64, description="注册时携带的访客ID，用于认领匿名报告")


class LoginRequest(BaseModel):
    username: str
    password: str
    visitorId: str | None = Field(default=None, max_length=64, description="登录时携带的访客ID，用于认领匿名报告")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录/注册响应。

    S6 修复（双凭证 XSS）：不再在响应体返回 ``access_token``。认证凭证统一通过
    httpOnly Cookie（``om_auth``，path=/，SameSite=strict，生产 Secure）下发，JS 无法
    读取该 Cookie，从根本上消除 XSS 窃取 token 的攻击面。响应体仅回传用户资料。
    """

    user: UserResponse


# ===== Helpers =====


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str) -> str:
    """签发 JWT。payload 携带 jti，供登出时精准拉黑单个 token。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": uuid.uuid4().hex,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ===== httpOnly Cookie 鉴权（P1-4）：token 存 httpOnly Cookie，防 XSS 窃取 =====
COOKIE_NAME = "om_auth"


def _extract_token(request: Request) -> str | None:
    """双轨取 token：Cookie(httpOnly) 优先，Authorization Bearer 兜底（兼容旧客户端）。"""
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


def _set_auth_cookie(response: Response, token: str, request: Request) -> None:
    # P1 修复（S3）：生产环境强制 secure=True，避免 Cookie 经明文链路被中间人窃取。
    # 开发环境（http）保持 secure=False 以便 localhost 调试可用。
    secure = settings.is_production
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


# ===== 限流阈值（登录/注册等敏感接口，防暴力破解）=====
# 阈值收敛到 settings（Q5）：auth_rate_limit / auth_rate_window。


def _client_ip(request: Request) -> str:
    """取客户端 IP（用于登录/注册限流）。

    S7 修复（速率限制可绕过）：仅在确认部署在可信反代后（``settings.proxy_trusted=True``）
    才信任 ``X-Forwarded-For`` 首段；否则一律使用 ``request.client.host``（真实连接 IP）。
    直连暴露时攻击者可任意伪造 XFF 变换 IP 绕过限流，故默认不信任 XFF。
    """
    if settings.proxy_trusted:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _guard_auth_rate(request: Request, action: str) -> None:
    """登录/注册限流：超限直接 429。Redis 不可用时退化为内存计数。"""
    ip = _client_ip(request)
    if await rate_limit_hit(f"{action}:{ip}", settings.auth_rate_limit, settings.auth_rate_window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"尝试过于频繁，请 {settings.auth_rate_window} 秒后重试。",
        )


async def _claim_visitor_reports(user: User, visitor_id: str | None, scene: str) -> int:
    """登录/注册时认领访客匿名报告，带 Redis 互斥锁防并发重复执行。

    拿不到锁直接跳过（说明已有并发请求在处理），失败不影响登录主流程。
    认领走独立 session 提交（P1-7），与本请求事务无关。
    """
    if not visitor_id:
        return 0
    if not await acquire_visitor_lock(visitor_id):
        logger.info("[migrate] visitor=%s 已有并发迁移，跳过", visitor_id[:8])
        return 0
    try:
        return await migrate_visitor_reports(user, visitor_id)
    except Exception:
        logger.warning("%s认领访客报告失败（不影响主流程）", scene, exc_info=True)
        return 0
    finally:
        await release_visitor_lock(visitor_id)


async def _resolve_user(
    db: AsyncSession,
    token: str | None,
    *,
    required: bool,
) -> User | None:
    """共用 token 解析 + 拉黑 + 封禁校验（Q3：消除 get_current_user / get_optional_user 重复，防逻辑漂移）。

    - ``required=True``：鉴权失败（无 token / 解码错 / 已拉黑 / 用户不存在 / 已封禁）一律抛 401/403，
      供 ``get_current_user`` 使用。
    - ``required=False``：上述任一情况均返回 ``None``（降为匿名），供 ``get_optional_user`` 使用，
      且不吞掉非预期异常（S5：瞬时 DB 错误 / 时钟偏差等不静默降级）。
    """
    if not token:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证凭证。")
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except jwt.PyJWTError:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid or expired.")
        return None
    except (KeyError, ValueError):
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token payload malformed.")
        return None
    # 登出 / 改密拉黑：即使 token 未过期也拒绝（required 抛错，可选降匿名）
    if await is_jwt_blacklisted(str(payload.get("jti") or "")):
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
        return None
    # P1 修复（S2）：封禁用户即使持合法 token 也拒绝 / 在可选端点降为匿名，使封禁真正生效
    if user.is_banned:
        if required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被封禁。")
        return None
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT 鉴权依赖：从 Cookie(httpOnly) 或 Authorization header 解析 token 并返回 User。

    P1-4 起优先读 httpOnly Cookie（防 XSS 窃取），Bearer 仅作兼容兜底。
    """
    token = _extract_token(request)
    return await _resolve_user(db, token, required=True)


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选鉴权依赖：带合法 token 则返回 User，否则返回 None（不抛错）。

    用于 reports 等接口：登录用户按账号隔离，匿名用户按 visitorId 隔离。
    P1-4 起 Cookie(httpOnly) 优先，Bearer 兜底。
    """
    token = _extract_token(request)
    return await _resolve_user(db, token, required=False)


# ===== 匿名身份解析（S9 加固）=====


async def get_visitor_id(
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
    visitor_id_q: str | None = Query(default=None, alias="visitorId", max_length=64),
) -> str | None:
    """解析匿名身份 visitorId（S9 加固）。

    - 优先取请求头 ``X-Visitor-Id``：避免 visitorId 出现在 URL / 访问日志 / Referer /
      浏览器历史中（缺陷报告 S9 的核心泄露面）。
    - URL 查询参数 ``visitorId`` 作为兼容回退（旧前端仍可用）。
    - 统一格式校验：非法字符或超长一律视为无效匿名身份返回 ``None``，
      不抛错（避免泄露资源存在性），后续 owner 过滤会因 ``None`` 直接返回空。
    """
    vid = x_visitor_id or visitor_id_q
    if not vid:
        return None
    if not is_valid_visitor_id(vid):
        return None
    return vid


# ===== Routes =====


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """注册新用户：限流 → 校验用户名唯一 → 哈希密码 → 签发 JWT。"""
    await _guard_auth_rate(request, "register")

    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' already exists.",
        )

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    await db.flush()  # 拿到 user.id 供签发 token / 审计引用，仍在事务内（未提交）

    token = create_access_token(user.id, user.username)
    # 审计：注册（合规 §4.6）—— 与 user 同一事务，一次 commit 一起落库（P1-5）
    await audited_commit(db, "register", "user", user.id)
    await db.refresh(user)
    # 认领放到主事务提交之后（P1-7）：认领走独立 session/事务，既不污染注册事务，
    # 也避免 SQLite 下第二个连接与主事务争写锁（放 commit 前会 database is locked）；
    # 且注册失败回滚时不会留下悬挂认领。
    await _claim_visitor_reports(user, req.visitorId, "注册")
    # S6：token 仅经 httpOnly Cookie 下发，响应体不再返回 access_token（消除双凭证 XSS 暴露面）
    _set_auth_cookie(response, token, request)
    return TokenResponse(
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """用户名 + 密码登录：限流 → 校验密码 → 签发 JWT。"""
    await _guard_auth_rate(request, "login")

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误。",
        )

    token = create_access_token(user.id, user.username)
    # 审计：登录（合规 §4.6）—— 审计行随本次请求事务提交（P1-5）
    await audited_commit(db, "login", "user", user.id)
    # 认领同样放到主事务提交之后（P1-7，理由同注册）
    await _claim_visitor_reports(user, req.visitorId, "登录")
    # S6：token 仅经 httpOnly Cookie 下发，响应体不再返回 access_token（消除双凭证 XSS 暴露面）
    _set_auth_cookie(response, token, request)
    return TokenResponse(
        user=UserResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息（依赖 httpOnly Cookie 自动携带）。"""
    return UserResponse.model_validate(user)


class LogoutResponse(BaseModel):
    """登出结果。"""

    revoked: bool
    detail: str = ""


@router.post("/auth/logout", response_model=LogoutResponse, summary="登出（拉黑当前 token + 清 Cookie）")
async def logout(request: Request, response: Response):
    """登出：把当前 token 的 jti 加入黑名单，并清除 httpOnly Cookie。

    - token 来源：优先 Cookie(httpOnly)，兜底 Authorization header；
    - 拉黑后多实例共享失效（依赖 Redis，降级到内存）；
    - 前端登出应调用本接口，并清除本地非敏感缓存标识（om_cache_owner）。
    """
    token = _extract_token(request)
    if not token:
        _clear_auth_cookie(response)
        return LogoutResponse(revoked=False, detail="未携带凭证")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        _clear_auth_cookie(response)
        return LogoutResponse(revoked=False, detail="token 已失效，无需拉黑")

    jti = str(payload.get("jti") or "")
    if not jti:
        _clear_auth_cookie(response)
        return LogoutResponse(revoked=False, detail="旧版 token 无 jti，清除本地副本即可")

    exp = payload.get("exp")
    ttl = int(exp - datetime.now(timezone.utc).timestamp()) if isinstance(exp, (int, float)) \
        else settings.jwt_expire_minutes * 60
    if ttl <= 0:
        _clear_auth_cookie(response)
        return LogoutResponse(revoked=False, detail="token 已过期")

    await blacklist_jwt(jti, ttl)
    _clear_auth_cookie(response)
    return LogoutResponse(revoked=True, detail=f"已拉黑，{ttl} 秒后自然过期")
