"""一次性数据迁移：SQLite -> PostgreSQL。

把开发/历史库（SQLite）中的全部业务数据搬到生产库（PostgreSQL）。
schema 已由 Alembic 在目标库建好（先 `alembic upgrade head`），本脚本只搬数据。

设计要点：
- 用 SQLAlchemy async 双引擎，按外键依赖顺序（metadata.sorted_tables）逐表对拷，
  保证子表在父表之后插入，不会破坏 FK。
- 加密字段（birth 等，存的是 Fernet 密文 `enc::...`）原样搬运，依赖部署到 PG 时使用
  **相同的 ENCRYPTION_KEY**，因此无需解密。
- alembic_version 置为 head，避免 PG 在下次 `alembic upgrade head` 时重复建表。
- `--reset` 会先清空目标库业务表（仅本脚本搬运的表 + alembic_version），便于重跑。

用法：
    SOURCE_DATABASE_URL='sqlite+aiosqlite:///C:/Users/67588/oraclemind_run.db' \
    DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/oraclemind' \
    python scripts/migrate_sqlite_to_pg.py [--reset]

说明：
- 目标库 DATABASE_URL 取环境变量（即生产 PG）；源库取 SOURCE_DATABASE_URL，
  缺省回退到开发库路径并打告警。
- 建议在迁移前对源库先跑一次 backup_db.py 兜底。
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# 允许以脚本方式直接运行（python scripts/migrate_sqlite_to_pg.py）
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import delete, insert, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

import app.models  # noqa: F401  —— 注册全部 ORM 模型
from app.db.base import Base  # noqa: E402

DEFAULT_SOURCE = "sqlite+aiosqlite:///C:/Users/67588/oraclemind_run.db"
_VERSIONS_DIR = _BACKEND_ROOT / "migrations" / "versions"


def _discover_head_revision() -> str:
    """扫描 versions/ 找到 down_revision 为 None 的迁移（即 baseline / head）。"""
    rev_re = re.compile(r"^revision\s*=\s*[\"']([^\"']+)[\"']", re.M)
    down_re = re.compile(r"^down_revision\s*=\s*(None|[\"']?[0-9a-f]+[\"']?)", re.M)
    head = None
    for f in _VERSIONS_DIR.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        m = down_re.search(src)
        if m and m.group(1).strip() == "None":
            r = rev_re.search(src)
            if r:
                head = r.group(1)
                break
    if not head:
        raise RuntimeError("未能在 migrations/versions 中找到 head 迁移（down_revision=None）")
    return head


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_async_engine(url, connect_args={"check_same_thread": False})
    return create_async_engine(url)


async def _count(conn, table) -> int:
    row = (await conn.execute(select(table))).fetchall()
    return len(row)


async def main(reset: bool) -> None:
    source_url = os.environ.get("SOURCE_DATABASE_URL") or DEFAULT_SOURCE
    target_url = os.environ.get("DATABASE_URL")
    if not target_url:
        raise SystemExit("缺少环境变量 DATABASE_URL（目标 PostgreSQL）。请设置后再运行。")
    if "sqlite" in target_url.lower() and not os.environ.get("ALLOW_SQLITE_TARGET"):
        raise SystemExit(
            "DATABASE_URL 指向 SQLite，本脚本用于迁往 PostgreSQL，已中止以避免误操作。"
            "（本地逻辑测试可用 ALLOW_SQLITE_TARGET=1 绕过）"
        )

    head = _discover_head_revision()
    tables = Base.metadata.sorted_tables
    table_names = [t.name for t in tables]

    print(f"[src ] {source_url}")
    print(f"[tgt ] {target_url}")
    print(f"[head] alembic_version -> {head}")
    print(f"[tbl ] {', '.join(table_names)}")

    src_engine = _make_engine(source_url)
    tgt_engine = _make_engine(target_url)

    try:
        async with src_engine.connect() as src:
            # ---- reset（可选）----
            if reset:
                print("\n[reset] 清空目标库业务表 + alembic_version ...")
                async with tgt_engine.begin() as tgt:
                    existing = set(await tgt.run_sync(lambda c: __import__("sqlalchemy").inspect(c).get_table_names()))
                    for table in reversed(tables):
                        if table.name in existing:
                            await tgt.execute(delete(table))
                    if "alembic_version" in existing:
                        await tgt.execute(text("DELETE FROM alembic_version"))

            # ---- 对拷（按依赖顺序）----
            async with tgt_engine.begin() as tgt:
                print("\n[copy] 开始按外键顺序对拷 ...")
                for table in tables:
                    result = await src.execute(select(table))
                    rows = [dict(r._mapping) for r in result.fetchall()]
                    if rows:
                        await tgt.execute(insert(table), rows)
                    print(f"  - {table.name}: {len(rows)} 行")
                # 置 head，避免重复建表
                await tgt.execute(
                    text(
                        "INSERT INTO alembic_version(version_num) VALUES (:v) "
                        "ON CONFLICT (version_num) DO NOTHING"
                    ),
                    {"v": head},
                )
                print(f"  - alembic_version: stamped {head}")

        # ---- 校验行数 ----
        print("\n[verify] 源 vs 目标 行数比对 ...")
        async with tgt_engine.connect() as tgt:
            async with src_engine.connect() as src2:
                mismatches = []
                for table in tables:
                    s = await _count(src2, table)
                    d = await _count(tgt, table)
                    flag = "OK" if s == d else "MISMATCH"
                    if s != d:
                        mismatches.append(table.name)
                    print(f"  - {table.name}: src={s} tgt={d} [{flag}]")
                av = (await tgt.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
                print(f"  - alembic_version: {[r[0] for r in av]}")

        if mismatches:
            raise SystemExit(f"行数不一致：{mismatches}")
        print("\n[done] 迁移完成，目标库已与源库数据一致。")
    finally:
        await src_engine.dispose()
        await tgt_engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SQLite -> PostgreSQL 一次性数据迁移")
    parser.add_argument("--reset", action="store_true", help="迁移前清空目标库业务表")
    args = parser.parse_args()
    asyncio.run(main(args.reset))
