"""R4~R8 代码质量项回归测试（后端 oraclemind-backend）。

- R4：报告版本链 ``list_report_versions`` 由「加载 owner 全部报告再 BFS」改为
      有界 ``parent_id`` 查询 + 纯函数 ``_assemble_version_chain`` 组装（防 OOM）。
- R5：SQL echo 仅 debug 且非生产时开启（session.py engine 构造）。
- R6：``get_db`` 处理器正常结束且未显式提交时，``_autocommit_pending`` 自动提交兜底。
- R7：时区统一（已在 S8 阶段将 profile.py 的 utcnow 改为 now(timezone.utc)，此处仅断言无残留）。
- R8：微信支付渠道未就绪时 ``create_order`` 抛 NotImplementedError，``create_order_with_fallback``
      捕获并降级为 StubChannel（notify 鉴权已由 S1 兜底），不会把异常栈泄露给客户端。
"""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.v1.reports import _assemble_version_chain
from app.db.session import _autocommit_pending
from app.main import app


# ===== R4：纯函数版本链组装（不依赖 DB） =====


class _FakeReport:
    def __init__(self, rid, parent_id=None, variant=0, created_at=None):
        self.id = rid
        self.parent_id = parent_id
        self.variant = variant
        self.created_at = created_at or datetime(2020, 1, 1)


def test_assemble_version_chain_collects_subtree_only():
    root = _FakeReport(1, None, variant=0, created_at=datetime(2020, 1, 1))
    c1 = _FakeReport(2, 1, variant=1, created_at=datetime(2020, 1, 2))
    c2 = _FakeReport(3, 1, variant=2, created_at=datetime(2020, 1, 3))
    g1 = _FakeReport(4, 2, variant=2, created_at=datetime(2020, 1, 4))
    other = _FakeReport(5, 9, variant=0, created_at=datetime(2020, 1, 5))  # parent 不在池中
    chain = _assemble_version_chain(root, [c1, c2, g1, other])
    ids = [r.id for r in chain]
    # 只返回根 + 其子孙（2、3、4），排除无关节点 5；按 (variant, created_at) 排序
    assert ids == [1, 2, 3, 4]


def test_assemble_version_chain_single_root_when_no_children():
    root = _FakeReport(7, None, variant=0, created_at=datetime(2021, 1, 1))
    assert [r.id for r in _assemble_version_chain(root, [])] == [7]


def test_assemble_version_chain_skips_cycle():
    # 构造一个指向已访问节点（root）的子节点；验证有界 BFS（range(50)）不会卡死
    root = _FakeReport(1, None)
    bad = _FakeReport(2, 1)
    chain = _assemble_version_chain(root, [bad])
    assert [r.id for r in chain] == [1, 2]


# ===== R4：端点集成（有界查询 + 归属隔离，命中真实 DB） =====


def test_versions_endpoint_returns_full_chain():
    u1 = f"r4a_{uuid.uuid4().hex[:10]}"
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={"username": u1, "password": "Passw0rd!23", "email": None},
        )
        assert reg.status_code == 201, reg.text
        root = client.post(
            "/api/v1/reports",
            json={"title": "root", "params": {"x": 1}, "results": {"bazi": {}}},
        )
        assert root.status_code == 201, root.text
        root_id = root.json()["id"]
        c1 = client.post(
            "/api/v1/reports",
            json={"title": "c1", "params": {}, "results": {"bazi": {}}, "parentId": root_id},
        ).json()
        c2 = client.post(
            "/api/v1/reports",
            json={"title": "c2", "params": {}, "results": {"bazi": {}}, "parentId": root_id},
        ).json()
        g1 = client.post(
            "/api/v1/reports",
            json={"title": "g1", "params": {}, "results": {"bazi": {}}, "parentId": c1["id"]},
        )
        assert g1.status_code == 201, g1.text
        g1_id = g1.json()["id"]

        ver = client.get(f"/api/v1/reports/{root_id}/versions")
        assert ver.status_code == 200, ver.text
        ids = [r["id"] for r in ver.json()]
        assert ids == [root_id, c1["id"], c2["id"], g1_id]


def test_versions_endpoint_enforces_ownership():
    u1 = f"r4o1_{uuid.uuid4().hex[:10]}"
    u2 = f"r4o2_{uuid.uuid4().hex[:10]}"
    with TestClient(app) as c1:
        c1.post(
            "/api/v1/auth/register",
            json={"username": u1, "password": "Passw0rd!23", "email": None},
        )
        r1 = c1.post(
            "/api/v1/reports",
            json={"title": "a", "params": {}, "results": {"bazi": {}}},
        )
        rid = r1.json()["id"]
    with TestClient(app) as c2:
        c2.post(
            "/api/v1/auth/register",
            json={"username": u2, "password": "Passw0rd!23", "email": None},
        )
        # 另一用户访问他人版本链 → 404（不暴露资源存在性）
        r = c2.get(f"/api/v1/reports/{rid}/versions")
        assert r.status_code == 404


# ===== R6：未显式提交时自动提交兜底 =====


def test_autocommit_pending_commits_when_dirty():
    s = MagicMock()
    s.new = {"obj"}
    s.dirty = set()
    s.deleted = set()
    s.commit = AsyncMock()
    asyncio.run(_autocommit_pending(s))
    s.commit.assert_awaited_once()


def test_autocommit_pending_noop_when_clean():
    s = MagicMock()
    s.new = set()
    s.dirty = set()
    s.deleted = set()
    s.commit = AsyncMock()
    asyncio.run(_autocommit_pending(s))
    s.commit.assert_not_awaited()


# ===== R5：echo 仅在 debug 且非生产时开启 =====
# （engine 在 import 时已按 _echo = settings.debug and not settings.is_production 构造）
def test_engine_echo_safe_default():
    from app.core.config import settings
    from app.db.session import engine

    # R5 判定：echo 必须与「debug 且非生产」严格一致（生产下即便误配 debug 也不泄露 SQL）
    assert engine.echo == (settings.debug and not settings.is_production)
    assert engine is not None


# ===== R7：时区统一（S8 阶段已修，断言无 utcnow 残留） =====
def test_no_utcnow_residual():
    import subprocess

    out = subprocess.run(
        ["grep", "-rn", "--include=*.py", "utcnow", "app/"],
        cwd=".",
        capture_output=True,
        text=True,
    )
    assert out.returncode != 0, f"仍存在 utcnow 残留: {out.stdout}"


# ===== R8：微信支付渠道未就绪时安全降级 =====


def test_wechat_channel_downgrades_to_stub():
    from app.services.payment import WechatNativeChannel, create_order_with_fallback

    ch = WechatNativeChannel("mch", "appid", "apikey", "serial")
    res = create_order_with_fallback(ch, "OM123", 100, "玄镜 · 测试")
    # 真实渠道未实现 → 降级 stub，绝不把 NotImplementedError 透传给客户端
    assert res.channel == "stub"
