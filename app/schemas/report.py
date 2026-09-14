"""报告服务 Pydantic 模型。"""

import json
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import is_valid_visitor_id

MAX_SEARCH_LEN = 64
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Q2 体积上限：报告入参序列化后的字节上限，挡住异常大的 payload 撑爆存储/内存。
REPORT_PARAMS_MAX_BYTES = 64 * 1024       # params（排盘输入）≤ 64KB
REPORT_RESULTS_MAX_BYTES = 2 * 1024 * 1024  # results（排盘结果快照）≤ 2MB
REPORT_SUMMARY_MAX_BYTES = 64 * 1024     # summary ≤ 64KB


class ReportCreate(BaseModel):
    """创建报告请求体（字段命名与前端一致：camelCase）。

    - visitorId：访客ID，匿名（未登录）时必填，用于隔离；已登录时可省略（归属账号）
    - params：排盘输入参数（出生信息/时辰/性别/问题等）
    - results：各术数排盘结果快照，key 为术数名（bazi/ziwei/liuyao/meihua/qimen/numerology）
    """

    visitorId: str | None = Field(default=None, max_length=64, description="访客ID（匿名云存储标识；已登录可省略）")
    title: str = Field(default="命理综合报告", max_length=64, description="报告标题")
    params: dict = Field(default_factory=dict, description="排盘输入参数")
    results: dict = Field(default_factory=dict, description="各术数排盘结果快照")
    summary: dict | None = Field(default=None, description="综合运势摘要（预留 AI 生成）")
    # 版本链（#12）：「换个说法」生成新报告时挂到上一版，便于回溯
    parentId: int | None = Field(default=None, description="父报告ID（换个说法的版本链）")
    variant: int = Field(default=0, ge=0, le=99, description="版本号：根版本 0，换个说法第 N 次为 N")

    @field_validator("visitorId")
    @classmethod
    def _check_visitor_id(cls, v: str | None) -> str | None:
        # S9 加固：匿名身份凭证必须合规，防止异常值绕过隔离或污染存储。
        # 已登录用户可省略 visitorId（落空串），空串视为「无访客」放行；仅拒绝非空的非法值。
        if v is not None and v != "" and not is_valid_visitor_id(v):
            raise ValueError("visitorId 格式非法")
        return v

    @field_validator("params")
    @classmethod
    def _check_params_size(cls, v: dict) -> dict:
        # Q2：排盘输入体积上限，防异常大 payload
        if len(json.dumps(v, ensure_ascii=False).encode("utf-8")) > REPORT_PARAMS_MAX_BYTES:
            raise ValueError("params 体积超限（≤64KB）")
        return v

    @field_validator("results")
    @classmethod
    def _check_results_size(cls, v: dict) -> dict:
        # Q2：排盘结果快照体积上限，防撑爆存储/内存
        if len(json.dumps(v, ensure_ascii=False).encode("utf-8")) > REPORT_RESULTS_MAX_BYTES:
            raise ValueError("results 体积超限（≤2MB）")
        return v

    @field_validator("summary")
    @classmethod
    def _check_summary_size(cls, v: dict | None) -> dict | None:
        # Q2：摘要体积上限
        if v is not None and len(json.dumps(v, ensure_ascii=False).encode("utf-8")) > REPORT_SUMMARY_MAX_BYTES:
            raise ValueError("summary 体积超限（≤64KB）")
        return v


class ReportOut(ReportCreate):
    """报告完整详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    favorited: bool = False
    pinned: bool = False
    parentId: int | None = None
    variant: int = 0


class ReportListItem(BaseModel):
    """报告列表项（不含完整 results，控制列表体积）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    visitorId: str
    title: str
    params: dict
    types: list[str] = Field(default_factory=list, description="报告包含的术数类型")
    created_at: datetime
    favorited: bool = False
    pinned: bool = False
    parentId: int | None = None
    variant: int = 0


class ReportSearch(BaseModel):
    """云端报告搜索条件（#2：关键词 + 日期范围 + 收藏筛选）。

    - q：匹配标题 / 提问 / 术数类型，大小写不敏感；最长 64 字符，超长直接拒绝
      （防止构造超长 LIKE 模式拖慢 SQLite 全表扫描）
    - dateFrom / dateTo：`YYYY-MM-DD`；dateTo 按「当天 23:59:59」处理，符合用户直觉
    - favorited：true 时只要收藏项
    """

    q: str | None = Field(default=None, max_length=MAX_SEARCH_LEN, description="关键词（标题/提问/术数）")
    dateFrom: str | None = Field(default=None, description="起始日期 YYYY-MM-DD")
    dateTo: str | None = Field(default=None, description="结束日期 YYYY-MM-DD")
    favorited: bool | None = Field(default=None, description="仅看收藏")

    @field_validator("dateFrom", "dateTo")
    @classmethod
    def _check_date(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not DATE_RE.match(v):
            raise ValueError("日期格式须为 YYYY-MM-DD")
        # 真实日历校验：2026-02-31 这类应被拒绝，否则会静默返回空结果
        datetime.strptime(v, "%Y-%m-%d")
        return v

    @field_validator("q")
    @classmethod
    def _strip_q(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class ReportFavoriteUpdate(BaseModel):
    """收藏/置top 更新请求（#5）。"""

    favorited: bool | None = Field(default=None, description="收藏状态")
    pinned: bool | None = Field(default=None, description="置顶状态")


class ReportBatchDelete(BaseModel):
    """批量删除请求（#7）。

    ids 上限 100：与列表 limit 上限一致，避免一次请求删空整库。
    """

    ids: list[int] = Field(..., min_length=1, max_length=100, description="待删除报告ID列表")


class AnnotationCreate(BaseModel):
    """新建批注（#8）。"""

    reportId: int = Field(..., description="所属报告ID")
    visitorId: str | None = Field(default=None, max_length=64, description="访客ID（匿名时必填）")
    anchor: str = Field(default="", max_length=64, description="锚点：summary / cards.1 / dims.事业")

    @field_validator("visitorId")
    @classmethod
    def _check_annotation_visitor_id(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_visitor_id(v):
            raise ValueError("visitorId 格式非法")
        return v
    anchorLabel: str = Field(default="", max_length=128, description="锚点展示名")
    quote: str = Field(default="", max_length=512, description="被批注原文片段")
    content: str = Field(..., min_length=1, max_length=2000, description="批注正文")


class AnnotationUpdate(BaseModel):
    """更新批注内容。"""

    content: str = Field(..., min_length=1, max_length=2000, description="批注正文")


class AnnotationOut(BaseModel):
    """批注详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reportId: int
    anchor: str = ""
    anchorLabel: str = ""
    quote: str = ""
    content: str = ""
    created_at: datetime
    updated_at: datetime
