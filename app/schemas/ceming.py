"""测字 / 姓名五格 / 合婚 —— 请求 / 响应模型（P2-2）。

汉字笔画由调用方传入（前端 cnchar 字典更全），后端只负责确定性算法，
因此请求里带的是 strokes 数组而非原始汉字。
"""

from pydantic import BaseModel, Field


# ===== 五格剖象 =====
class WugeRequest(BaseModel):
    surname: str = Field(..., max_length=8, description="姓（1~2 字）")
    given: str = Field(..., max_length=8, description="名（1~3 字）")
    surnameStrokes: list[int] = Field(..., min_length=1, max_length=2, description="姓各字笔画")
    givenStrokes: list[int] = Field(..., min_length=1, max_length=3, description="名各字笔画")


class WugeResponse(BaseModel):
    surname: str
    given: str
    grids: dict = Field(..., description="五格（tian/ren/di/wai/zong）：数理、吉凶、五行")
    threeTalent: dict = Field(..., description="三才配置（天/人/地五行与评断）")
    score: int = Field(..., ge=0, le=100, description="综合评分")
    incomplete: bool = Field(default=False, description="是否存在取不到笔画的字（结果仅供参考）")


# ===== 合婚 =====
class HehunRequest(BaseModel):
    maleZhi: str = Field(..., description="男方年支（生肖地支，如 '午'）")
    femaleZhi: str = Field(..., description="女方年支（生肖地支）")
    maleGan: str | None = Field(default=None, description="男方日干（可选，用于天干五合）")
    femaleGan: str | None = Field(default=None, description="女方日干（可选）")
    maleWuxing: dict[str, int] | None = Field(default=None, description="男方五行计数（可选）")
    femaleWuxing: dict[str, int] | None = Field(default=None, description="女方五行计数（可选）")


class HehunResponse(BaseModel):
    maleZodiac: str
    femaleZodiac: str
    relations: dict = Field(..., description="六合/六冲/六害/三合/三刑/天干五合 是否命中")
    verdict: str = Field(..., description="生肖关系结论")
    level: str = Field(..., description="上吉 / 吉 / 平 / 凶")
    complement: dict = Field(default_factory=dict, description="五行互补情况")
    missingBoth: list[str] = Field(default_factory=list, description="双方都缺的五行")
    score: int = Field(..., ge=0, le=100, description="合婚评分")


# ===== 测字 =====
class CeziRequest(BaseModel):
    char: str = Field(..., min_length=1, max_length=4, description="要测的汉字（取首字）")
    strokes: int | None = Field(default=None, ge=1, le=64, description="笔画数（可选）")


class CeziResponse(BaseModel):
    char: str
    element: str = Field(..., description="五行取象")
    trigram: dict = Field(..., description="配卦（name / sym / nature）")
    tendency: str = Field(..., description="走势倾向")
    strokes: int | None = None
    codePoint: int = Field(..., description="码点（供前端复算校验）")


# ===== 八字合婚（P2-4：用八字推导的日干 + 五行计数，复用 compute_hehun）=====
class HehunBaziRequest(BaseModel):
    maleDayGan: str = Field(..., description="男方日干（如 '甲'）")
    femaleDayGan: str = Field(..., description="女方日干")
    maleWuxing: dict[str, int] = Field(..., description="男方八字五行计数 {金:0,木:0,...}")
    femaleWuxing: dict[str, int] = Field(..., description="女方八字五行计数")
    maleZhi: str | None = Field(default=None, description="男方年支（可选，用于生肖六合/冲害）")
    femaleZhi: str | None = Field(default=None, description="女方年支（可选）")
