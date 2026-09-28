"""量表相关 Pydantic 模型（对外 API 的数据契约）。

约定：对外字段用 camelCase（与前端、既有 premium schema 一致）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScaleQuestion(BaseModel):
    """单题（对外只暴露题干与选项，不暴露计分细节）。"""

    id: str
    text: str
    dimension: str
    options: list[dict] = Field(default_factory=list)


class ScaleDimension(BaseModel):
    key: str
    name: str


class ScaleListItem(BaseModel):
    """量表列表卡片（轻量）。"""

    slug: str
    title: str
    tagline: str
    description: str
    estimatedMinutes: int
    questionCount: int


class ScaleDetail(BaseModel):
    """量表详情（含题目与选项，供前端渲染答题）。"""

    slug: str
    title: str
    tagline: str
    description: str
    disclaimer: str
    estimatedMinutes: int
    options: list[dict] = Field(default_factory=list)
    dimensions: list[ScaleDimension] = Field(default_factory=list)
    questions: list[ScaleQuestion] = Field(default_factory=list)


class ScaleScoreSubmit(BaseModel):
    """提交作答：{item_id: 1–5}。"""

    answers: dict[str, int] = Field(..., description="题目ID→作答值（1–5）")


class DimensionScore(BaseModel):
    key: str
    name: str
    score: int
    band: str
    interpretation: str


class ScaleScoreResult(BaseModel):
    slug: str
    dimensions: list[DimensionScore] = Field(default_factory=list)
    summary: str
    disclaimer: str
    # 作答落库后的记录 ID（前端用于关联 AI 心理报告 / 个人中心留存）；无归属时为空串
    attemptId: str = ""
