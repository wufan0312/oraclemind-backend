"""排盘服务 —— 统一请求 / 响应模型（字段命名与前端 JS 一致：camelCase）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaipanRequest(BaseModel):
    """排盘入参（八字 / 紫微 / 六爻 / 梅花 / 奇门 共用）。

    出生时间：hour（0-23）与 timeText（如 "辰时"）二选一；
    timeText 优先级高（hour 为 None 时用 timeText 换算）。
    """

    year: int = Field(..., ge=1900, le=2100, description="出生年份（公历）")
    month: int = Field(..., ge=1, le=12, description="出生月份（公历）")
    day: int = Field(..., ge=1, le=31, description="出生日期（公历）")
    hour: int | None = Field(None, ge=0, le=23, description="出生小时 0-23（与 timeText 二选一）")
    timeText: str = Field("", description="时辰文本：子时~亥时 / 不详")
    gender: str = Field("男", description="性别：男 / 女 / 其他")
    question: str = Field("", description="所问问题（六爻/梅花取用神参考）")
    method: str = Field("time", description="起卦方式：六爻 time/coin/manual；梅花 time/number/text/manual")
    linesInput: list[int] | None = Field(None, description="手动/摇钱起卦的 6 爻编码（自下而上）：0少阳 1少阴 2老阳动 3老阴动")
    num1: int | None = Field(None, description="梅花数字起卦：第一个报数")
    num2: int | None = Field(None, description="梅花数字起卦：第二个报数")
    shangNum: int | None = Field(None, description="梅花手动指定：上卦数 1-8（先天数）")
    xiaNum: int | None = Field(None, description="梅花手动指定：下卦数 1-8（先天数）")
    dongNum: int | None = Field(None, description="梅花手动指定：动爻 1-6")
    numType: str | None = Field(None, description="梅花应期取数类型：xian 先天数 / hou 后天数（洛书）")
    qimen_ju: dict | None = Field(None, description="奇门手动定局：{'yinyang': '阳'/'阴', 'ju': 1-9}；为 null 时走自动拆补法")
    lunar: "LunarInput | None" = Field(
        None,
        description="农历生日（可选，优先于 year/month/day 用于换算公历）。"
        "month 负数表示闰月（如 -8 = 闰八月）。前端只原样上送录入的农历分量，不预换算。",
    )
    longitude: float | None = Field(
        None,
        ge=-180,
        le=180,
        description="出生地经度（东经为正，如北京 116.4 / 乌鲁木齐 87.6）。"
        "传入后由后端对**生辰类**排盘（八字 / 紫微）做真太阳时校正（分钟级，可跨日）。"
        "缺省或超出中国陆地范围（73~135）时不校正，行为与旧版一致。",
    )
    minute: int | None = Field(
        0,
        ge=0,
        le=59,
        description="出生分钟 0-59。配合 longitude 使用：真太阳时校正以分钟为单位，"
        "只给 hour 时按整点（0 分）处理。",
    )


class LunarInput(BaseModel):
    """农历生日分量（前端原样上送，后端权威换算公历）。"""

    model_config = ConfigDict(extra="ignore")

    year: int = Field(..., ge=1900, le=2100, description="农历年份")
    month: int = Field(..., ge=-12, le=12, description="农历月份（1-12，闰月为负数）")
    day: int = Field(..., ge=1, le=30, description="农历日期")


def resolve_lunar_to_solar(req: "PaipanRequest | ZiweiTimelineRequest") -> None:
    """若请求携带农历生日，则在后端权威换算为公历并覆盖 year/month/day。

    前端不再承担农历→公历换算，只负责把用户录入的农历分量原样上送；
    后端统一用 lunar-python 换算，避免前后端历法实现不一致。换算失败时
    保留前端上送的公历（兜底）。
    """
    lunar = getattr(req, "lunar", None)
    if lunar is None:
        return
    try:
        from lunar_python import Lunar as LP

        solar = LP.fromYmd(lunar.year, lunar.month, lunar.day).getSolar()
        req.year = solar.getYear()
        req.month = solar.getMonth()
        req.day = solar.getDay()
    except Exception:
        # 历法换算失败：保留前端上送的公历兜底，不阻断排盘
        pass


def apply_true_solar(req: "PaipanRequest | ZiweiTimelineRequest") -> dict | None:
    """真太阳时校正：**就地**改写 req 的 year/month/day/hour/minute，返回校正详情。

    仅用于**生辰类**排盘（八字 / 紫微）。问事类（六爻 / 梅花 / 奇门）以起卦时刻立极，
    且起卦地未必是出生地，套用出生地经度反而失真，故这些路由不调用本函数。

    返回 None 表示未校正（经度缺失或非法 / 时辰不详），调用方保持原值即可 ——
    校正是增强项，任何失败都静默降级为钟表时间，绝不阻断排盘。
    """
    from app.services.paipan.true_solar import compute_true_solar, shichen_to_hour

    lng = getattr(req, "longitude", None)
    if lng is None:
        return None

    # 小时优先取显式入参；没给 hour 时从 timeText 折算（区间中点）。
    # 两者都拿不到（如 timeText="不详"）则不校正 —— 宁可用钟表时间，也不要拿假时刻硬算。
    hour = getattr(req, "hour", None)
    if hour is None:
        hour = shichen_to_hour(getattr(req, "timeText", "") or "")
    if hour is None:
        # 时辰不详（"不详" / 空）：不拿假时刻硬算
        return None

    info = compute_true_solar(
        req.year,
        req.month,
        req.day,
        int(hour),
        int(getattr(req, "minute", 0) or 0),
        lng,
    )
    if info is None:
        return None

    # 注意：必须在构造 paipan_cache 的 key（req.model_dump()）**之前**调用，
    # 这样校正后的时刻会进入缓存键，不同经度不会互相命中旧结果。
    req.year, req.month, req.day = info["year"], info["month"], info["day"]
    req.hour, req.minute = info["hour"], info["minute"]
    return info


class ZiweiTimelineRequest(BaseModel):
    """紫微斗数 流年/流月 指定年份查询入参（出生信息 + 目标年/月）。"""

    year: int = Field(..., ge=1900, le=2100, description="出生年份（公历）")
    month: int = Field(..., ge=1, le=12, description="出生月份（公历）")
    day: int = Field(..., ge=1, le=31, description="出生日期（公历）")
    hour: int | None = Field(None, ge=0, le=23, description="出生小时 0-23（与 timeText 二选一）")
    timeText: str = Field("", description="时辰文本：子时~亥时 / 不详")
    gender: str = Field("男", description="性别：男 / 女 / 其他")
    targetYear: int = Field(..., ge=1900, le=2100, description="查询目标公历年份（流年）")
    targetMonth: int | None = Field(None, ge=1, le=12, description="查询目标农历月份 1-12（流月）；省略则返回该年 12 流月列表")
    lunar: "LunarInput | None" = Field(
        None,
        description="农历生日（可选，优先于 year/month/day 用于换算公历）。month 负数表示闰月。",
    )
    longitude: float | None = Field(None, ge=-180, le=180, description="出生地经度（东经为正）；传入则做真太阳时校正")
    minute: int | None = Field(0, ge=0, le=59, description="出生分钟 0-59（配合 longitude 做分钟级校正）")


class BasePaipanResponse(BaseModel):
    """排盘结果基类：核心字段显式声明，其余排盘字段透传（extra=allow）。

    各术数输出结构不同（嵌套 dict/list），响应体即为完整排盘 dict——
    前端可直接消费（与 numerology 的平铺结构一致）。
    """

    model_config = ConfigDict(extra="allow")

    solar: str = Field(..., description="公历日期 YYYY-MM-DD")
    lunar: str = Field(..., description="农历日期字符串")
    timeText: str = Field(..., description="时辰文本")
