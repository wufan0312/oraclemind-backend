"""P1 审批 Gate 核心单测（不拉起 app.main，避免 settings 重依赖）。

用 async sqlite 内存库验证 ApprovalService 状态机 + verify_approval 校验 +
consumed 防重放 + 跨身份拒绝 + action 不匹配拒绝。

运行：
    PYTHONPATH=<backend_root> python oraclemind-backend/tests/test_approvals.py
"""

import asyncio

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.approval import ApprovalService, verify_approval
from app.models.approval import Approval
from app.models import Approval as ApprovalRegistered  # 验证已在 models/__init__ 注册


async def make_maker():
    """构造独立内存库 + 仅建 approvals 表的 sessionmaker。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Approval.__table__.create)
    return maker


async def _request(maker, **kw):
    svc = ApprovalService()
    async with maker() as db:
        appr = await svc.request(
            db, action_type="donation", actor_type="visitor", actor_id="v1", summary="供养", **kw
        )
        await db.commit()
        return appr.id


async def test_request_pending():
    maker = await make_maker()
    async with maker() as db:
        a = await ApprovalService().request(db, action_type="donation", actor_type="visitor", actor_id="v1", summary="s")
        await db.commit()
        assert a.status == "pending", a.status
        assert a.id is not None


async def test_approve_verify_consume_replay():
    maker = await make_maker()
    aid = await _request(maker)
    # approve
    async with maker() as db:
        a = await ApprovalService().approve(db, aid, actor_type="visitor", actor_id="v1")
        await db.commit()
        assert a.status == "approved"
    # verify ok
    async with maker() as db:
        appr = await verify_approval(db, aid, expected_action_type="donation", actor_type="visitor", actor_id="v1")
        assert appr.id == aid
        await ApprovalService().consume(db, aid)
        await db.commit()
    # replay 被拒（已消费）
    async with maker() as db:
        try:
            await verify_approval(db, aid, expected_action_type="donation", actor_type="visitor", actor_id="v1")
            raise AssertionError("已消费的审批应被拒绝")
        except HTTPException as e:
            assert e.status_code in (409, 428), e.status_code


async def test_verify_pending_rejected():
    maker = await make_maker()
    aid = await _request(maker)
    async with maker() as db:
        try:
            await verify_approval(db, aid, expected_action_type="donation", actor_type="visitor", actor_id="v1")
            raise AssertionError("pending 应通过 428 被拒")
        except HTTPException as e:
            assert e.status_code == 428, e.status_code


async def test_reject_blocks():
    maker = await make_maker()
    aid = await _request(maker)
    async with maker() as db:
        await ApprovalService().reject(db, aid, actor_type="visitor", actor_id="v1", note="no")
        await db.commit()
    async with maker() as db:
        try:
            await verify_approval(db, aid, expected_action_type="donation", actor_type="visitor", actor_id="v1")
            raise AssertionError("rejected 应通过 428 被拒")
        except HTTPException as e:
            assert e.status_code == 428, e.status_code


async def test_cross_actor_forbidden():
    maker = await make_maker()
    aid = await _request(maker)
    async with maker() as db:
        try:
            await ApprovalService().approve(db, aid, actor_type="visitor", actor_id="OTHER")
            raise AssertionError("跨身份审批应被 403 拒绝")
        except HTTPException as e:
            assert e.status_code == 403, e.status_code


async def test_action_mismatch():
    maker = await make_maker()
    aid = await _request(maker)
    async with maker() as db:
        await ApprovalService().approve(db, aid, actor_type="visitor", actor_id="v1")
        await db.commit()
    async with maker() as db:
        try:
            await verify_approval(db, aid, expected_action_type="premium", actor_type="visitor", actor_id="v1")
            raise AssertionError("action 不匹配应通过 428 被拒")
        except HTTPException as e:
            assert e.status_code == 428, e.status_code


async def test_list_for():
    maker = await make_maker()
    await _request(maker)
    async with maker() as db:
        rows = await ApprovalService().list_for(db, "visitor", "v1")
        assert len(rows) == 1, len(rows)
        rows2 = await ApprovalService().list_for(db, "visitor", "v2")
        assert len(rows2) == 0, len(rows2)


async def test_model_registered():
    assert ApprovalRegistered is Approval


async def main():
    tests = [
        test_request_pending,
        test_approve_verify_consume_replay,
        test_verify_pending_rejected,
        test_reject_blocks,
        test_cross_actor_forbidden,
        test_action_mismatch,
        test_list_for,
        test_model_registered,
    ]
    passed = 0
    for t in tests:
        try:
            await t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} PASS")
    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
