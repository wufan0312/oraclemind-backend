"""应用配置 —— pydantic-settings 读取 .env / 环境变量。

所有配置项集中在此，避免散落各处硬编码。
新增配置：在此处加字段，并在 .env.example 中补充说明。

【环境变量值的容错处理】
云平台（Vercel / Railway 等）的环境变量面板经常被人为污染，实际踩到过的形态：
  - 成对引号：`DEBUG="false"`、`JWT_EXPIRE_MINUTES="10080"`
    → 布尔/整数字段直接 ValidationError 启动失败；
    → 字符串字段更阴险：`APP_ENV="production"` 会让 is_production 判 False，
      从而**静默跳过** JWT_SECRET 强度校验与 SQLite 拦截（安全语义被绕过）。
  - CRLF 残留：Windows 记事本另存后再复制粘贴，值尾部带 `\\r`。
  - 行内注释：`JWT_EXPIRE_MINUTES=10080  # 7 天`。

因此统一在「校验之前」做一次清洗（去首尾空白与引号，数值字段额外去行内注释）。
洁癖无损：这些配置项本身不会有首尾空格或引号，清洗只会让脏输入变成正确输入。
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 布尔字面量白名单（pydantic 原生仅认 true/false/1/0，这里补上常见的 yes/no/on/off）
_BOOL_TRUE = frozenset({"1", "true", "t", "yes", "y", "on"})
_BOOL_FALSE = frozenset({"0", "false", "f", "no", "n", "off", ""})

# 需要「整数语义 + 明确报错」的字段，供统一校验器复用
_INT_FIELDS = (
    "port",
    "jwt_expire_minutes",
    "donation_expire_minutes",
    "auth_rate_limit",
    "auth_rate_window",
    "search_scan_cap",
    "stash_max_keys",
    "stash_max_bytes",
)
_BOOL_FIELDS = ("debug", "proxy_trusted")


def _clean_env_value(raw: Any) -> Any:
    """清洗环境变量标量：去首尾空白（含 CRLF 残留）与成对引号。"""
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    return s


def _clean_number_token(raw: Any) -> Any:
    """在 _clean_env_value 之上，再去掉行内注释（`#` 之后），供数值/布尔字段使用。"""
    s = _clean_env_value(raw)
    if isinstance(s, str) and "#" in s:
        s = s.split("#", 1)[0].strip()
    return s


# 支持的环境标识（APP_ENV 取值白名单）
_KNOWN_ENVS = ("development", "production", "test")


def _current_env() -> str:
    """读取当前环境标识。

    判定顺序：
      1. APP_ENV 显式设置且在白名单内  → 用它（Vercel 面板 / 终端 export）
      2. 未设置，但检测到 Vercel 平台（VERCEL=1）→ production
      3. 其余情况 → development

    第 2 条是防呆：Vercel 会自动注入 VERCEL=1。若忘了在面板配 APP_ENV，
    没有这一条就会回落 development，加载 .env.development 把 CORS 设成
    localhost、DEBUG 设成 true —— 线上既跨域失败又泄露 SQL 日志。
    """
    env = str(_clean_env_value(os.environ.get("APP_ENV") or "")).strip().lower()
    if env:
        return env if env in _KNOWN_ENVS else "development"
    if str(_clean_env_value(os.environ.get("VERCEL") or "")).strip().lower() == "1":
        return "production"
    return "development"


def _env_files() -> tuple[str, ...]:
    """按 APP_ENV 组装 env 文件列表（**越靠后优先级越高**）。

    最终优先级（高 → 低）：
      1. 真实环境变量（Vercel 项目面板 / 终端 export）
      2. .env.<APP_ENV>   —— 随仓库提交的环境默认值（团队共享）
      3. .env            —— 个人本地兜底（gitignore，可放本机路径 / 密钥）

    pydantic-settings 天然保证「环境变量 > env 文件」，且 env_file 元组中
    靠后的文件覆盖靠前的，因此这个顺序正好实现「线上用面板、本地用 .env」。

    这里用绝对路径而非相对路径：Vercel / uvicorn 的工作目录不保证是项目根，
    相对 ".env" 会静默读不到文件（表现为配置回落默认值，极难排查）。
    """
    root = Path(__file__).resolve().parents[2]  # app/core/config.py → 项目根
    return (str(root / ".env"), str(root / f".env.{_current_env()}"))


class Settings(BaseSettings):
    """全局配置。字段名与 .env 中的键一一对应（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 环境变量容错（见模块头 docstring）=====
    @field_validator("*", mode="before")
    @classmethod
    def _normalize_env_scalars(cls, v: Any) -> Any:
        """所有字段统一去空白/引号，避免 `"production"` 这类脏值静默改变语义。"""
        return _clean_env_value(v)

    @field_validator(*_BOOL_FIELDS, mode="before")
    @classmethod
    def _parse_bool_fields(cls, v: Any, info: ValidationInfo) -> Any:
        """布尔字段：容忍引号/空格/行内注释，并给出可定位的报错。"""
        s = _clean_number_token(v)
        if isinstance(s, str):
            low = s.lower()
            if low in _BOOL_TRUE:
                return True
            if low in _BOOL_FALSE:
                return False
            raise ValueError(
                f"环境变量 {info.field_name.upper()} 需为布尔值"
                f"（true/false/1/0/yes/no/on/off），实际收到 {v!r}"
            )
        return s

    @field_validator(*_INT_FIELDS, mode="before")
    @classmethod
    def _parse_int_fields(cls, v: Any, info: ValidationInfo) -> Any:
        """整数字段：容忍引号/空格/行内注释；空值回落默认值，非法值明确报错。"""
        s = _clean_number_token(v)
        if isinstance(s, str):
            if s == "":
                return cls.model_fields[info.field_name].default
            try:
                return int(s)
            except ValueError:
                raise ValueError(
                    f"环境变量 {info.field_name.upper()} 需为整数，实际收到 {v!r}"
                ) from None
        return s

    @field_validator("log_level", mode="before")
    @classmethod
    def _parse_log_level(cls, v: Any) -> str:
        """日志级别：空值/非法值回退 INFO，避免启动崩溃（Vercel 面板可能存空串）。"""
        s = _clean_env_value(v)
        if not s:
            return "INFO"
        up = s.upper()
        if up in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            return up
        return "INFO"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: Any) -> Any:
        """把云厂商给的「裸 scheme」补全为异步驱动。

        Neon/Supabase 控制台复制出来的常是 `postgres://` 或 `postgresql://`（不带驱动后缀）。
        SQLAlchemy 会据此加载**同步**驱动 psycopg2，随后 create_async_engine 抛
        "The asyncio extension requires an async driver" —— 而这发生在 **import 期**，
        在 Vercel 上表现为 500 FUNCTION_INVOCATION_FAILED 且响应体为空，几乎无法定位。
        这里统一补成 postgresql+asyncpg://；Alembic 侧 migrations/env.py 的 _sync_url
        会自动把它转回 psycopg2，两边都成立。
        """
        s = _clean_env_value(v)
        if isinstance(s, str) and s:
            low = s.lower()
            if low.startswith("postgres://"):
                return "postgresql+asyncpg://" + s[len("postgres://") :]
            if low.startswith("postgresql://"):
                return "postgresql+asyncpg://" + s[len("postgresql://") :]
        return s

    @field_validator("encryption_key", mode="after")
    @classmethod
    def _check_encryption_key(cls, v: str) -> str:
        """把 ENCRYPTION_KEY 归一化成合法 Fernet 密钥，非法值早失败并给出可操作报错。

        否则 cryptography 会在 import 期抛英文 ValueError，在 Vercel 上同样只是
        一个没有 body 的 500，面板填错值（带引号/截断/非 base64）时排查成本极高。
        留空表示回退到 jwt_secret 派生（仅开发可用），此处不拦。

        容错：面板上很常见的「32 字节随机 hex」（`openssl rand -hex 32`、
        `secrets.token_hex(32)`，共 64 个字符）并非 Fernet 期望的 url-safe base64。
        这种值**字节层面完全合法**，只是编码不同，这里直接换算成等价 Fernet 密钥，
        避免为了换个编码而再折腾一轮面板 + Redeploy。
        （换算是一一对应的：同一 hex 永远得到同一个 Fernet 密钥，不会导致存量密文解不开。）
        """
        if not v:
            return v
        import base64
        import binascii

        from cryptography.fernet import Fernet  # 局部导入：避免顶层耦合

        # ① 已经是合法 Fernet 密钥
        try:
            Fernet(v.encode())
            return v
        except Exception:  # noqa: BLE001 - 继续尝试下面的容错形态
            pass

        # ② 64 位 hex（32 字节原始密钥）→ url-safe base64
        try:
            raw = binascii.unhexlify(v)
        except (binascii.Error, ValueError):
            raw = b""
        if len(raw) == 32:
            return base64.urlsafe_b64encode(raw).decode()

        # ③ 43 位 base64（漏了结尾的 '=' 填充）
        if len(v) == 43:
            padded = v + "="
            try:
                Fernet(padded.encode())
                return padded
            except Exception:  # noqa: BLE001
                pass

        raise ValueError(
            "ENCRYPTION_KEY 不是合法的 Fernet 密钥：应为 32 字节密钥，"
            "编码为 url-safe base64（44 字符，结尾 '='）或 64 位 hex。"
            "请检查 Vercel 面板的值是否含引号/空格/被截断，并重新生成："
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    # ===== 应用 =====
    app_name: str = "玄镜 OracleMind 后端"
    app_version: str = "0.1.0"
    app_env: str = "development"  # development / production
    # S8 修复：默认值偏安全（False）。开发期若想看 SQLAlchemy echo 调试日志再显式置 True。
    # 之前默认 True 时，一旦生产漏配 APP_ENV=production，engine.echo 会把含绑定参数的 SQL
    # 打到 stdout，造成参数泄露风险。
    debug: bool = False
    log_level: str = "INFO"

    # ===== 服务 =====
    host: str = "0.0.0.0"
    port: int = 8000

    # ===== 数据层（规划文档 §5：PostgreSQL 主库 + Redis 缓存）=====
    # 开发环境可用 sqlite+aiosqlite:///./oraclemind.db（PG 不可达时降级）
    database_url: str = "sqlite+aiosqlite:///./oraclemind.db"
    redis_url: str = "redis://localhost:6379/0"

    # ===== JWT 认证 =====
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 天

    # ===== 字段级加密（敏感数据：出生信息等，见缺陷报告 P0-4）=====
    # 留空则回退到 jwt_secret 派生密钥（仅开发可用）；生产环境务必设置独立强随机密钥。
    # 生成命令：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # ===== 随喜供养支付（#1：渠道可插拔）=====
    # 未配置商户号时自动降级为 stub 渠道（返回占位引导，不产生真实交易）；
    # 配齐以下四项后自动切换到真实微信支付 Native 下单。
    wechat_mch_id: str = ""
    wechat_app_id: str = ""
    wechat_api_v3_key: str = ""
    wechat_notify_url: str = ""  # 支付结果回调地址（需公网可达）
    # 商户 API 证书序列号（native 下单需要）
    wechat_serial_no: str = ""
    # 订单有效期（分钟），超期未支付自动失效
    donation_expire_minutes: int = 30

    # ===== 敏感接口限流（登录/注册防暴力破解，原散落于 auth.py 局部常量，Q5 收敛）=====
    auth_rate_limit: int = 10   # 固定窗口内允许的最大尝试次数
    auth_rate_window: int = 60  # 窗口长度（秒）

    # ===== 边界 / 扫描上限（Q5 收敛）=====
    # 报告列表内存搜索候选上限：单身份报告量上限约 100，留 10 倍余量覆盖，
    # 同时挡住「全表拉进内存」的 OOM 风险（原 _SEARCH_SCAN_CAP）。
    search_scan_cap: int = 1000
    # 上云 KV（stash）单身份资源上限（原无限制，Q2 加固）：
    stash_max_keys: int = 200            # 单身份最多键数
    stash_max_bytes: int = 5_000_000     # 单身份 value 总字节上限（约 5MB）

    # ===== 支付回调鉴权（P0 修复：防伪造 success 免费解锁付费权益）=====
    # 供自有/代理渠道或 stub 本地模拟真实回调使用的回调令牌。
    # 配置后，/premium/notify 与 /donations/notify 必须携带匹配令牌（header X-Payment-Token）才处理订单；
    # 令牌缺失/不匹配直接拒绝且绝不信任 payload.success。
    # 未配置时：生产环境（APP_ENV=production）自动拒绝回调（403，防伪造），开发环境放行（本地便利）。
    # 生成命令：python -c "import secrets; print(secrets.token_urlsafe(32))"
    payment_callback_secret: str = ""

    @property
    def wechat_pay_enabled(self) -> bool:
        """是否已配齐微信支付凭证（决定走真实支付还是 stub 降级）。"""
        return all([
            self.wechat_mch_id,
            self.wechat_app_id,
            self.wechat_api_v3_key,
            self.wechat_serial_no,
        ])

    @property
    def is_sqlite(self) -> bool:
        """是否使用 SQLite（决定 engine 参数与 SQL 方言）。"""
        return "sqlite" in self.database_url.lower()

    # ===== CORS（前端 Next.js 开发/生产地址）=====
    # 3000=默认 dev；3001=端口冲突时 Next 自动切换；3311=生产预览
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3311"

    @property
    def cors_origin_list(self) -> list[str]:
        """解析逗号分隔的 CORS 来源为列表，并并入内置线上前端域名（去重、保序）。

        为什么内置：面板若配了「错的或空的」CORS_ORIGINS（本项目就曾误配成同名撞车域名
        oraclemind.vercel.app），或 .env.production 未被上传到构建环境，白名单会退化成
        localhost —— 线上前端被静默拒绝跨域，且不产生任何报错，排查极其费时。
        内置域名做并集兜底后，env 仍然生效且可继续追加，只是不再可能把线上链路打穿。
        """
        parsed = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return list(dict.fromkeys([*parsed, "https://oraclemind-frontend.vercel.app"]))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    # ===== 反向代理信任（P1 修复 S3）=====
    # 为 true 时启用 Starlette ProxyHeadersMiddleware，信任 X-Forwarded-* 头
    # （仅当部署在可信反代后，否则客户端可伪造来源/协议）。默认 false 关闭，避免误信。
    # 配合「生产强制 Cookie secure」使用：若反代 TLS 终结且开启本项，request.url.scheme 才正确。
    proxy_trusted: bool = False

    @property
    def is_vercel(self) -> bool:
        """是否运行在 Vercel 平台（Vercel 会注入 VERCEL=1）。"""
        return os.environ.get("VERCEL", "") == "1"

    def validate_for_runtime(self) -> None:
        """生产/Vercel 环境禁止使用 SQLite。

        Vercel 函数实例使用临时只读文件系统，SQLite 文件会在每次部署/冷启动后丢失，
        且多实例间不共享。因此 staging/prod 必须由 DATABASE_URL 指向 PostgreSQL。
        在 dev（app_env=development）下使用 SQLite 是允许的。
        """
        if (self.is_production or self.is_vercel) and self.is_sqlite:
            raise RuntimeError(
                "生产/Vercel 环境检测到 SQLite database_url，已阻止启动。\n"
                "Vercel 文件系统是临时的，SQLite 数据会在每次部署后丢失。\n"
                "请在环境变量 DATABASE_URL 中配置 PostgreSQL，例如：\n"
                "  postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>\n"
                "然后用 `alembic upgrade head` 在 PG 上建表。"
            )

        # JWT 密钥校验：生产环境禁止空或保留默认占位符，否则攻击者可伪造任意用户 token。
        # 占位符 "change-me-in-production" 随源码公开，若生产沿用，认证形同虚设
        # （任意人都可用该密钥签发 admin 等高权限 token，完全绕过登录）。
        if self.is_production and (
            not self.jwt_secret or self.jwt_secret == "change-me-in-production"
        ):
            raise RuntimeError(
                "生产环境 JWT_SECRET 不可为空或保留默认值 'change-me-in-production'，已阻止启动。\n"
                "该默认值随源码公开，攻击者可借此伪造任意用户身份 token，完全绕过认证。\n"
                "请在环境变量 JWT_SECRET 配置强随机密钥，例如：\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
            )


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例（进程内只解析一次 .env）。"""
    return Settings()


settings = get_settings()
