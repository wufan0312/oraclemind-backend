"""Alembic 迁移环境 —— 自动发现 app.models 中注册的 ORM 模型。

数据库 URL 从 app.core.config.settings 注入，支持 SQLite（开发）/ PostgreSQL（生产）
按 .env 自动切换。Alembic 使用同步引擎执行迁移；async 驱动（aiosqlite / asyncpg）
在此转换为同步驱动（SQLite / psycopg2）。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

import app.models  # noqa: F401 —— 注册全部 ORM 模型，供 autogenerate 自动发现

config = context.config

# 注入运行时数据库 URL（覆盖 ini 中的占位），实现按 .env 切换
# 防御：空值会在 create_engine 里抛出晦涩的
#   "Could not parse SQLAlchemy URL from given URL string"
# 这里提前给出可执行的明确报错（最常见诱因：Vercel 环境变量 DATABASE_URL 未填或填成 ""）
_db_url = (settings.database_url or "").strip()
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL 未配置或为空。Vercel 构建期执行 `alembic upgrade head` 需要可连接的 "
        "PostgreSQL。\n请在 Vercel 项目 → Settings → Environment Variables 中设置 DATABASE_URL，"
        "格式：\n  postgresql+asyncpg://<user>:<password>@<host>/<db>?ssl=require"
        "&prepared_statement_cache_size=0\n"
        "（若想让构建不依赖数据库，可删除 vercel.json 中的 buildCommand，"
        "迁移将在函数冷启动时执行）"
    )
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url(url: str) -> str:
    """将 async 驱动转换为 Alembic 可用的同步驱动。"""
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite", 1)
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    return url


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    url = _sync_url(settings.database_url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # batch 仅在 SQLite 需要（SQLite 不支持原生 ALTER）；PG 下开启会触发整表重建，必须关闭
        render_as_batch=settings.is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url(settings.database_url)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # batch 仅在 SQLite 需要；PG 下开启会触发整表重建，必须关闭
            render_as_batch=settings.is_sqlite,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
