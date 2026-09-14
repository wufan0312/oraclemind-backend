"""SQLite 数据库备份脚本 —— 对应缺陷报告 P2-15（无数据库备份策略）。

用法：
    # 用项目 venv 运行（自动读取 .env 的 DATABASE_URL）
    .venv/Scripts/python.exe scripts/backup_db.py
    # 或显式指定库路径
    .venv/Scripts/python.exe scripts/backup_db.py --db /path/to/oraclemind_run.db

行为：
    - 仅支持 SQLite（当前后端实际使用的数据库）。
    - 将源库复制为带时间戳的副本到 ./backups/（脚本所在 backend 根目录下的 backups/）。
    - 复制完成后打印源/副本大小与 SHA-256，便于核对完整性。
    - 若源库不存在则报错退出（非零码），便于接入定时任务/CI 时感知失败。

说明：PostgreSQL 切换后（缺陷报告 P0-1）应改用 pg_dump；本脚本仅覆盖当前 SQLite 场景。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 允许以脚本方式直接运行：把 backend 根目录加入 sys.path 以便 import app
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

SQLITE_URL_RE = re.compile(r"^sqlite(\+\w+)?:///(?P<path>.+)$")


def _db_path_from_url(url: str) -> str | None:
    """从 SQLAlchemy SQLite URL 解析绝对路径。

    支持 ``sqlite:///abs/path`` 与 ``sqlite+aiosqlite:///C:/Users/...db``。
    相对路径（``sqlite:///./x.db``）按 backend 根目录解析。
    """
    m = SQLITE_URL_RE.match(url.strip())
    if not m:
        return None
    raw = m.group("path")
    # Windows 下可能出现 sqlite:///C:/... 或 sqlite:////C:/... 的情况
    raw = raw.lstrip("/")
    p = Path(raw)
    if not p.is_absolute():
        p = (BACKEND_ROOT / raw).resolve()
    return str(p)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup the OracleMind SQLite database.")
    parser.add_argument("--db", help="Explicit SQLite db path (overrides DATABASE_URL).")
    parser.add_argument(
        "--out-dir",
        default=str(BACKEND_ROOT / "backups"),
        help="Destination directory for backups (default: <backend>/backups).",
    )
    args = parser.parse_args()

    # 解析源库路径
    if args.db:
        src = Path(args.db).expanduser().resolve()
    else:
        try:
            from app.core.config import settings  # 延迟导入，便于 --db 模式离线运行
        except Exception as exc:  # pragma: no cover
            print(f"[backup] 无法加载配置（需先 pip install -r requirements）：{exc}", file=sys.stderr)
            return 2
        src_str = _db_path_from_url(settings.database_url)
        if not src_str:
            print(
                f"[backup] DATABASE_URL 不是 SQLite，本脚本不适用：{settings.database_url}\n"
                "         切换到 PostgreSQL 后请改用 pg_dump。",
                file=sys.stderr,
            )
            return 3
        src = Path(src_str)

    if not src.exists():
        print(f"[backup] 源库不存在：{src}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"oraclemind_{ts}.db"

    # 复制（SQLite 为单文件，直接 shutil.copy 即可；若服务在跑，SQLite 文件仍可被复制，
    # 但建议低峰期执行；生产 PG 场景应改用 pg_dump 一致性快照）
    shutil.copy2(src, dst)

    src_sha = _sha256(src)
    dst_sha = _sha256(dst)
    ok = src_sha == dst_sha
    print(f"[backup] 源库   : {src}  ({src.stat().st_size} bytes)")
    print(f"[backup] 副本   : {dst}  ({dst.stat().st_size} bytes)")
    print(f"[backup] SHA-256: {dst_sha}")
    print(f"[backup] 校验   : {'OK 一致' if ok else 'FAIL 不一致！'}")

    # 同时保留一份最新软链/固定名副本，便于一键回滚
    latest = out_dir / "oraclemind_latest.db"
    shutil.copy2(dst, latest)
    print(f"[backup] 最新副本: {latest}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
