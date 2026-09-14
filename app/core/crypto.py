"""字段级加密工具 —— 敏感数据（出生信息等）在 DB 层透明加密存储。

设计要点（对应缺陷报告 P0-4）：
- 采用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密，密钥由配置派生。
- 密文带固定前缀 ``enc::``，便于运行期区分「已加密」与「旧明文」数据，
  实现零停机兼容迁移（旧明文读出即原文，新写入一律加密）。
- 解密失败（如密钥轮换导致旧密文不可解）回退返回原文，避免数据读取中断。
- API 层返回前由 ORM 透明解密，业务代码无感知。

密钥策略：优先使用 settings.encryption_key；为空则回退到 jwt_secret 派生（仅限开发）。
生产应通过环境变量设置独立强随机密钥（见 config.encryption_key 注释）。
"""

import json
import logging
from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

# 密文标记前缀（明文数据不含此前缀）
PREFIX = "enc::"


def _build_fernet() -> Fernet:
    """由配置密钥派生 32 字节 url-safe 密钥并构造 Fernet 实例。

    P1 修复（S4）：禁止回退到通用硬编码字符串或复用 JWT 密钥。
    - 配置了独立 ``encryption_key`` → 优先使用；
    - 未配置 + 开发环境 → 回退到 ``jwt_secret`` 派生并告警（仅限本地便利）；
    - 未配置 + 生产环境 → **直接拒绝启动**，避免敏感出生信息以近似明文存储。
    """
    raw = settings.encryption_key
    if raw:
        source = "encryption_key"
    elif not settings.is_production:
        raw = settings.jwt_secret
        source = "jwt_secret(dev 回退)"
        logger.warning(
            "ENCRYPTION_KEY 未配置，开发环境回退使用 JWT 密钥派生字段级加密密钥（仅限本地）；"
            "生产环境必须配置独立的 ENCRYPTION_KEY，否则敏感出生信息近似明文存储。"
        )
    else:
        raise RuntimeError(
            "生产环境必须配置独立的 ENCRYPTION_KEY（字段级加密密钥），"
            "禁止复用 JWT 密钥或默认回退，否则敏感出生信息近似明文存储。\n"
            "生成：python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if not raw:
        raise RuntimeError("字段级加密密钥为空：encryption_key 与 jwt_secret 均未配置。")
    key = urlsafe_b64encode(sha256(raw.encode("utf-8")).digest())
    logger.info("字段级加密密钥已加载（来源=%s）", source)
    return Fernet(key)


_fernet = _build_fernet()


def encrypt_value(plaintext: str | dict | list) -> str:
    """将明文（字符串或 JSON 对象）加密为 ``enc::<token>`` 格式。

    接受 str（原样加密）或 dict/list（先 json.dumps 再加密），便于直接加密结构化出生信息。
    """
    if not isinstance(plaintext, str):
        plaintext = json.dumps(plaintext, ensure_ascii=False)
    token = _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{PREFIX}{token}"


def decrypt_value(maybe: str | None) -> str | None:
    """解密 ``enc::<token>`` 密文；非密文（旧明文）原样返回；解密失败回退原文。

    兼容性：迁移期 DB 中既可能有旧明文 JSON，也可能有本模块密文，
    二者都能被正确处理，保证零停机切换。

    P1 修复（S5）：仅捕获 ``InvalidToken``（密钥不匹配，多为密钥轮换后的旧密文），
    其余异常（数据损坏、编解码错误等）**不再吞掉**，交由全局异常处理器记录 traceback
    并返回 500，避免把密文当明文静默返回导致「数据看似正常实则丢失」。
    """
    if not maybe:
        return maybe
    if not maybe.startswith(PREFIX):
        return maybe  # 旧明文数据，直接返回
    try:
        return _fernet.decrypt(maybe[len(PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # 密钥不匹配：多为密钥轮换后的旧密文。返回原文占位并告警（非静默），
        # 相关字段将不可用，需重新生成或迁移。
        logger.warning(
            "解密失败（InvalidToken，可能为密钥轮换后的旧密文）：该字段将返回密文占位，"
            "相关数据不可用。value_prefix=%s",
            maybe[:16],
        )
        return maybe
