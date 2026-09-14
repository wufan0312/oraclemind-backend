# -*- coding: utf-8 -*-
"""天使数字 —— 请求 / 响应模型（字段命名与前端 JS 一致：camelCase）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AngelEntry(BaseModel):
    """单条天使数字释义（与前端 AngelEntry 一致）。"""

    model_config = ConfigDict(extra="ignore")

    n: str = Field(..., description="序列（如 '111' / '1234'）")
    title: str = Field(..., description="主标题")
    core: str = Field(..., description="核心含义")
    advice: str = Field(..., description="行动建议")
    love: str | None = Field(None, description="感情提示（可选）")
    career: str | None = Field(None, description="事业/财富提示（可选）")


class AngelParseRequest(BaseModel):
    """单个数解析入参。"""

    raw: str = Field(
        ...,
        max_length=512,
        description="原始输入：接受 '1111' / '11:11' / '1 2 3' / 带空格或分隔符的任意串。"
        "超长（归一化后 > 12 位）由服务层判为 400，而非 500。",
    )


class AngelParseResponse(BaseModel):
    """单个数解析结果（与前端 AngelResult 同构，后端额外补 repDigit / digitalRoot）。"""

    raw: str = Field(..., description="归一化后的数字串（如 '1111'）")
    key: str = Field(..., description="命中的词条 key（如 '111'）")
    entry: AngelEntry = Field(..., description="命中的释义条目")
    isRepDigit: bool = Field(..., description="是否全同数字（如 2222）")
    isSequence: bool = Field(..., description="是否连续递增序列（如 1234）")
    digits: list[int] = Field(..., description="各位数字（去重保序）")
    repDigit: int | None = Field(None, description="重复数字：全同序列时为该项数字，否则 null")
    digitalRoot: int = Field(..., description="主数字（数字根）：未精确命中时的兜底口径")
    digitMeaning: dict[str, str] = Field(
        default_factory=dict, description="逐位释义（key 为数字字符字符串）"
    )


class AngelSequenceRequest(BaseModel):
    """序列分析入参：用户近期反复看到的多个数字。"""

    numbers: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="数字序列列表（每项都会归一化，最多 100 条）",
    )


class AngelSequenceItem(BaseModel):
    """序列分析 · 单条频次统计。"""

    raw: str = Field(..., description="归一化后的数字串")
    count: int = Field(..., description="出现次数")
    ratio: float = Field(..., description="占比（0~1）")
    key: str = Field(..., description="命中的词条 key")
    title: str = Field(..., description="命中词条标题")
    isRepDigit: bool = Field(False, description="是否全同数字")
    isSequence: bool = Field(False, description="是否连续递增序列")


class AngelSequenceResponse(BaseModel):
    """序列分析结果。"""

    total: int = Field(..., description="有效记录条数")
    unique: int = Field(..., description="去重后的序列数")
    invalid: list[str] = Field(default_factory=list, description="无法解析的原始输入")
    items: list[AngelSequenceItem] = Field(default_factory=list, description="频次表（降序）")
    top: list[AngelSequenceItem] = Field(default_factory=list, description="出现次数最多的（可能并列）")
    topKey: str = Field(..., description="主导词条 key")
    topEntry: AngelEntry = Field(..., description="主导词条释义")
    themes: list[str] = Field(default_factory=list, description="归纳出的主题关键词（按权重降序）")
    keyFrequency: dict[str, int] = Field(default_factory=dict, description="命中词条频次")
    digitFrequency: dict[str, int] = Field(default_factory=dict, description="单个数字出现频次")
    summary: str = Field(..., description="一句话归纳")


class AngelPersonalRequest(BaseModel):
    """个人天使数字入参。"""

    birthDate: str = Field(
        ...,
        max_length=32,
        description="出生日期：'YYYY-MM-DD' 或 'YYYYMMDD'",
    )
    name: str | None = Field(
        None,
        max_length=40,
        description="可选姓名；仅回显，不参与计算（避免混用毕达哥拉斯姓名数口径）",
    )


class AngelPersonalResponse(BaseModel):
    """个人天使数字结果（民俗算法，见服务层 docstring）。"""

    birthDate: str = Field(..., description="归一化后的出生日期 YYYY-MM-DD")
    name: str = Field("", description="姓名（回显）")
    lifePath: int = Field(..., description="生命数（数字根）1~9")
    birthdayNum: int = Field(..., description="生日数（数字根）")
    key: str = Field(..., description="映射到的天使数字词条 key（如 '777'）")
    entry: AngelEntry = Field(..., description="对应释义条目")
    personalNumber: str = Field(..., description="个人天使数字（生命数三位重复）")
    note: str = Field(..., description="算法依据免责说明")
