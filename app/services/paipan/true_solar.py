# -*- coding: utf-8 -*-
"""真太阳时校正 —— 生辰排盘（八字 / 紫微）的时间基准校正。

为什么需要
----------
中国全境统一使用北京时间（东经 120° 的平太阳时），但排盘定「时辰」依据的应是出生地的
真实太阳位置。乌鲁木齐（东经 87.6°）与北京（116.4°）的实际太阳时相差近 2 小时，
足以让时柱整体偏一个时辰 —— 时柱一错，八字四柱与紫微命盘（命宫由生月 + 生时推定）全盘皆错。

公式（与前端 `src/lib/trueSolarTime.ts` 同口径，保证前后端一致）
--------------------------------------------------------------
    真太阳时 = 北京时间 + (出生地经度 − 120°) × 4 分钟/度 + 时差 EoT

  · 经度差：地球自转 1° 合 4 分钟，偏东为早（加）、偏西为晚（减）；
  · EoT（Equation of Time）：真太阳时与平太阳时之差，由轨道偏心与黄赤交角导致，
    全年在 ±16 分钟内波动（2 月最慢 −14 分，11 月最快 +16 分）。

为什么下沉到后端
----------------
此前只有前端一份实现，且是「时辰 → 取区间中点 → 校正 → 再取整回时辰」的**有损往返**：
单次量化误差可达 ±1 小时，服务端拿到的还只是已经量化过的时辰文本。
后端在**分钟级**上完成校正后再定盘，前后端结果才对得上，也让「同一份入参 → 同一份命盘」
这条不变量成立（换客户端、换入口结果一致）。

结论仅供娱乐与传统文化参考，不构成任何决策依据。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

# 中国陆地经度范围：超出该范围视为非法/误填，不做校正（宁可用钟表时间，也不要算出离谱结果）
LNG_MIN, LNG_MAX = 73.0, 135.0

# 北京时间基准经线（东八区中央经线）
BASE_LONGITUDE = 120.0


def day_of_year(year: int, month: int, day: int) -> int:
    """一年中的第几天（1-366）。"""
    return date(year, month, day).timetuple().tm_yday


def equation_of_time(year: int, month: int, day: int) -> float:
    """时差 EoT（分钟）：标准近似公式，全年误差 < 1 分钟。"""
    n = day_of_year(year, month, day)
    b = 2.0 * math.pi * (n - 81) / 365.0
    return 9.87 * math.sin(2.0 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


# 时辰 → 小时（取**区间中点**，与各排盘服务的 _time_to_hour 同表，保证口径一致）：
# 子时 23:00-01:00 → 0 / 丑时 01:00-03:00 → 2 / 寅时 03:00-05:00 → 4 …
SHICHEN_MID_HOUR = {
    "子": 0, "丑": 2, "寅": 4, "卯": 6, "辰": 8, "巳": 10,
    "午": 12, "未": 14, "申": 16, "酉": 18, "戌": 20, "亥": 22,
}


def shichen_to_hour(time_text: str) -> int | None:
    """时辰文本 → 小时（区间中点）。无法识别（含「不详」）返回 None。

    与 bazi/ziwei/qimen 各服务内部的 _time_to_hour 保持同一张表，避免
    「校正模块」与「排盘模块」对同一时辰理解不同导致结果互相打架。
    """
    if not time_text:
        return None
    text = time_text.strip()
    for name, hour in SHICHEN_MID_HOUR.items():
        if text.startswith(name):
            return hour
    return None


def compute_true_solar(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    longitude: float | None = None,
) -> dict | None:
    """把北京时间（钟表时间）换算为真太阳时，必要时跨日。

    返回 None 表示输入非法 / 不足以校正（调用方应原样使用钟表时间），
    绝不抛异常 —— 校正只是锦上添花，不该阻断排盘主流程。
    """
    if longitude is None:
        return None
    try:
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (LNG_MIN <= lng <= LNG_MAX):
        return None

    try:
        hh = int(hour)
        mi = int(minute or 0)
        base = datetime(year, month, day, hh, mi)
    except (TypeError, ValueError):
        return None

    longitude_min = (lng - BASE_LONGITUDE) * 4.0
    eot_min = equation_of_time(year, month, day)
    total_min = longitude_min + eot_min

    corrected = base + timedelta(minutes=total_min)

    return {
        "lng": round(lng, 4),
        "longitudeMin": round(longitude_min, 2),
        "eotMin": round(eot_min, 2),
        "totalMin": round(total_min, 2),
        "clockTime": f"{hh:02d}:{mi:02d}",
        "correctedTime": corrected.strftime("%H:%M"),
        "dayOffset": (corrected.date() - base.date()).days,
        # 校正后的完整时刻：调用方直接用它覆盖原入参
        "year": corrected.year,
        "month": corrected.month,
        "day": corrected.day,
        "hour": corrected.hour,
        "minute": corrected.minute,
    }
