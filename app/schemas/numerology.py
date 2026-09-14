"""数字命理排盘 —— 请求 / 响应模型（字段命名与前端 JS 一致：camelCase）。"""

from pydantic import BaseModel, Field


class NumerologyRequest(BaseModel):
    """排盘入参：农历生日（年 / 月 / 日）。

    与前端校验一致（宽松校验：月 1-12、日 1-31），不做日历级校验——
    农历存在大月 30 天，且页面明确标注「输入农历生日」。
    """

    year: int = Field(..., ge=1900, le=2100, description="出生年份（农历）")
    month: int = Field(..., ge=1, le=12, description="出生月份（农历）")
    day: int = Field(..., ge=1, le=31, description="出生日期（农历）")
    name: str | None = Field(
        default=None, max_length=40,
        description="可选中文姓名，用于计算表现数 / 内驱数 / 人格数 / 成熟数（不传则只返回挑战数）",
    )


class ChallengeNumbers(BaseModel):
    """挑战数（4 个）：月 / 日 / 年各自化到个位后的两两差值。"""

    c1: int = Field(..., description="第一挑战：月−日，早年（0-35 岁）主课题")
    c2: int = Field(..., description="第二挑战：日−年，中年课题")
    c3: int = Field(..., description="第三挑战：第一−第二，贯穿一生的底层课题")
    c4: int = Field(..., description="第四挑战：月−年，面对世界的外部挑战")


class NumCore(BaseModel):
    """毕达哥拉斯核心数字（姓名相关三项可为空）。"""

    pinyin: str = Field(default="", description="姓名拼音转写（空名时为 ''）")
    unmatched: list[str] = Field(default_factory=list, description="未能识别的汉字，供前端提示")
    expression: int | None = Field(default=None, description="表现数：全名字母之和")
    soulUrge: int | None = Field(default=None, description="内驱数：元音字母之和")
    personality: int | None = Field(default=None, description="人格数：辅音字母之和")
    maturity: int | None = Field(default=None, description="成熟数：生命灵数 + 表现数")
    challenge: ChallengeNumbers = Field(..., description="挑战数")


class YearInfo(BaseModel):
    """单年流年信息。"""

    yr: int
    py: int
    tag: str
    isCurrent: bool


class NumDetail(BaseModel):
    """单个数字的完整解读。"""

    name: str
    element: str
    color: str
    keywords: str
    talent: str
    lesson: str
    career: str
    mate: str
    posi: str
    nega: str
    desc: str


class NumerologyResponse(BaseModel):
    """排盘结果 —— 与前端 computeNum 输出结构一致，前端可直接消费。"""

    lifePath: int = Field(..., description="生命灵数 1~9")
    birthdayNum: int = Field(..., description="生日数")
    counts: dict[int, int] = Field(..., description="九宫格统计（1~9 各数字出现次数）")
    missing: list[int] = Field(default_factory=list, description="缺数（出现 0 次的数字）")
    years: list[YearInfo] = Field(default_factory=list, description="未来 9 年流年（覆盖完整数字周期）")
    data: NumDetail = Field(..., description="生命灵数完整解读")
    core: NumCore = Field(..., description="核心数字（表现 / 内驱 / 人格 / 成熟 + 四挑战）")
