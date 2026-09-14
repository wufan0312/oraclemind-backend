"""S9 visitorId 弱隔离加固回归测试：

- 后端解析依赖 get_visitor_id：请求头 X-Visitor-Id 优先（避免进 URL/日志），查询参数兼容回退，
  非法字符/超长一律视为无效（返回 None，不泄露资源存在性）。
- 各请求体 schema 对 visitorId 做字符集白名单校验（UUID v4 / 前端降级串均合规）。
"""

import asyncio

import pytest
from pydantic import ValidationError

from app.api.v1.auth import get_visitor_id
from app.schemas.report import AnnotationCreate, ReportCreate
from app.schemas.donation import DonationCreate
from app.schemas.premium import PremiumOrderCreate


# ===== get_visitor_id 依赖 =====


def _vid(x=None, q=None):
    return asyncio.run(get_visitor_id(x_visitor_id=x, visitor_id_q=q))


def test_vid_prefers_header_over_query():
    # 头与查询同时存在：以头为准
    assert _vid(x="header-id-123", q="query-id-456") == "header-id-123"


def test_vid_falls_back_to_query():
    assert _vid(q="query-id-123") == "query-id-123"


def test_vid_absent_returns_none():
    assert _vid() is None


def test_vid_invalid_charset_returns_none():
    # 含空格/特殊字符：视为无效匿名身份
    assert _vid(q="bad id !!") is None
    # 超长（>64）：视为无效
    assert _vid(q="a" * 65) is None


def test_vid_valid_uuid_format_accepted():
    uuid_like = "9f1c2b3a-4d5e-4f6a-8b7c-0d1e2f3a4b5c"
    assert _vid(q=uuid_like) == uuid_like


# ===== schema 白名单校验 =====


def test_report_create_rejects_invalid_visitor_id():
    with pytest.raises(ValidationError):
        ReportCreate(visitorId="bad id !!", title="t", params={}, results={})


def test_report_create_accepts_valid_visitor_id():
    r = ReportCreate(visitorId="9f1c2b3a-4d5e-4f6a-8b7c-0d1e2f3a4b5c", title="t", params={}, results={})
    assert r.visitorId == "9f1c2b3a-4d5e-4f6a-8b7c-0d1e2f3a4b5c"
    r2 = ReportCreate.model_validate({"visitorId": "v-abc-123", "title": "t", "params": {}, "results": {}})
    assert r2.visitorId == "v-abc-123"


def test_annotation_create_rejects_invalid_visitor_id():
    with pytest.raises(ValidationError):
        AnnotationCreate(reportId=1, visitorId="!!", content="x")


def test_donation_create_rejects_invalid_visitor_id():
    with pytest.raises(ValidationError):
        DonationCreate(tier="诚意", visitorId="!!")


def test_premium_create_rejects_invalid_visitor_id():
    with pytest.raises(ValidationError):
        PremiumOrderCreate(itemId="tarot_deep", visitorId="!!")
