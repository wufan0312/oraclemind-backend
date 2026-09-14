"""配置安全启动校验测试（中优先级 #3：防生产漏配 jwt_secret 伪造 token）。

验证 Settings.validate_for_runtime() 对 JWT 密钥的强制校验：
- 生产环境 + 默认占位符 jwt_secret → RuntimeError（拒绝启动）
- 生产环境 + 空 jwt_secret → RuntimeError
- 生产环境 + 强随机 jwt_secret → 不抛异常
- 开发环境 + 默认占位符 jwt_secret → 不抛异常（本地便利）
（sqlite 校验的既有行为不在本文件覆盖，见原 init_db 启动链路）
"""

import pytest

from app.core.config import Settings


def test_prod_default_jwt_secret_rejected():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", jwt_secret="change-me-in-production").validate_for_runtime()


def test_prod_empty_jwt_secret_rejected():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", jwt_secret="").validate_for_runtime()


def test_prod_strong_jwt_secret_ok():
    # 不应抛异常
    Settings(
        app_env="production",
        jwt_secret="aB3kZ9xQ2mN7pL5vR1tY8wS4uC6dE0fG3hJ",
        database_url="postgresql+asyncpg://u:p@h:5432/db",
    ).validate_for_runtime()


def test_dev_default_jwt_secret_ok():
    # 开发环境允许保留默认占位符（本地便利）
    Settings(app_env="development", jwt_secret="change-me-in-production").validate_for_runtime()


def test_dev_sqlite_default_allowed():
    # 开发环境允许 SQLite（与既有 sqlite 校验语义一致）
    Settings(app_env="development", database_url="sqlite+aiosqlite:///./dev.db").validate_for_runtime()


def test_prod_sqlite_still_rejected():
    with pytest.raises(RuntimeError):
        Settings(
            app_env="production",
            database_url="sqlite+aiosqlite:///./dev.db",
            jwt_secret="aB3kZ9xQ2mN7pL5vR1tY8wS4uC6dE0fG3hJ",
        ).validate_for_runtime()
