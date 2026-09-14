# -*- coding: utf-8 -*-
"""奇门遁甲排盘 · 权威盘 cross-check（P2-1）。

对照《烟波钓叟歌》范式与标准安星规则，校验 compute_qimen 的：
  - 定局（局数表 / 符头→三元 / 节气取法）
  - 值符值使（旬首奇仪落宫之星/门）
  - 驿马（时支三合）
  - 空亡（六甲旬空）

不依赖"现在"，全部用固定日期 + 独立 oracle 复算，确保口径稳定。
"""
from lunar_python import Solar

from app.services.paipan.qimen import (
    compute_qimen, YANG_JU, YIN_JU, MA_TABLE, XUN_EMPTY,
    PALACE_STAR, PALACE_DOOR, XUNSHOU_QIYI, _dingyuan, PINYIN_TO_CN,
)

GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

QIYI_SEQ = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]


def _gz_index(gan: str, zhi: str) -> int:
    """六十甲子索引（独立复算，不调用被测函数）。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for k in range(6):
        if (gi + 10 * k) % 12 == zi:
            return gi + 10 * k
    return 0


# ===== 《烟波钓叟歌》定局口诀（权威基准）=====
SONG_YANG = {
    "冬至": (1, 7, 4), "惊蛰": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "春分": (3, 9, 6), "立春": (8, 5, 2), "雨水": (9, 6, 3), "清明": (4, 1, 7),
    "立夏": (4, 1, 7), "谷雨": (5, 2, 8), "小满": (5, 2, 8), "芒种": (6, 3, 9),
}
SONG_YIN = {
    "夏至": (9, 3, 6), "白露": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "秋分": (7, 1, 4), "立秋": (2, 5, 8), "处暑": (1, 4, 7), "寒露": (6, 9, 3),
    "立冬": (6, 9, 3), "霜降": (5, 8, 2), "小雪": (5, 8, 2), "大雪": (4, 1, 7),
}


def test_dingju_song_table():
    """局数表必须与《烟波钓叟歌》口诀逐字一致。"""
    assert YANG_JU == SONG_YANG, YANG_JU
    assert YIN_JU == SONG_YIN, YIN_JU


def test_dingyuan_mapping():
    """符头→三元：子午卯酉=上元(0)，寅申巳亥=中元(1)，辰戌丑未=下元(2)。"""
    assert _dingyuan("子") == 0 and _dingyuan("午") == 0
    assert _dingyuan("卯") == 0 and _dingyuan("酉") == 0
    assert _dingyuan("寅") == 1 and _dingyuan("申") == 1
    assert _dingyuan("巳") == 1 and _dingyuan("亥") == 1
    assert _dingyuan("辰") == 2 and _dingyuan("戌") == 2
    assert _dingyuan("丑") == 2 and _dingyuan("未") == 2


def test_ma_table():
    """驿马：申子辰→寅(3)，寅午戌→申(7)，巳酉丑→亥(6)，亥卯未→巳(4)。"""
    expect = {"申": 3, "子": 3, "辰": 3, "寅": 7, "午": 7, "戌": 7,
              "巳": 6, "酉": 6, "丑": 6, "亥": 4, "卯": 4, "未": 4}
    assert MA_TABLE == expect, MA_TABLE


def test_kongwang_table():
    """六甲旬空。"""
    expect = {0: ("戌", "亥"), 10: ("申", "酉"), 20: ("午", "未"),
              30: ("辰", "巳"), 40: ("寅", "卯"), 50: ("子", "丑")}
    assert XUN_EMPTY == expect, XUN_EMPTY


def _oracle_dingju(year: int, month: int, day: int, hour: int) -> str:
    """独立 oracle：复算定局（仅用权威常量 YANG_JU/YIN_JU + 标准三元规则）。"""
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lunar = solar.getLunar()
    day_gz = lunar.getDayInGanZhi()
    day_idx = _gz_index(day_gz[0], day_gz[1])
    xun = day_idx - day_idx % 10
    xun_zhi = ZHI[xun % 12]
    if xun_zhi in ("子", "午", "卯", "酉"):
        yuan = 0
    elif xun_zhi in ("寅", "申", "巳", "亥"):
        yuan = 1
    else:
        yuan = 2
    table = lunar.getJieQiTable()
    now_val = year * 10000 + month * 100 + day
    best, best_v = None, -1
    for name, sol in table.items():
        cn = PINYIN_TO_CN.get(name, name)  # 与被测代码一致：拼音键归一化为中文
        if cn not in YANG_JU and cn not in YIN_JU:
            continue
        v = sol.getYear() * 10000 + sol.getMonth() * 100 + sol.getDay()
        if v <= now_val and v > best_v:
            best, best_v = cn, v
    yy = "阳" if best in YANG_JU else "阴"
    ju = (YANG_JU if yy == "阳" else YIN_JU)[best][yuan]
    return f"{yy}遁{ju}局"


def test_dingju_end_to_end():
    """端到端：多个固定日期的定局应与独立 oracle 复算一致（覆盖阴阳遁/上中下元）。"""
    cases = [
        (2024, 12, 25, 12),  # 冬至 → 阳遁
        (2025, 1, 10, 12),   # 小寒 → 阳遁
        (2025, 3, 10, 12),   # 惊蛰 → 阳遁
        (2025, 5, 20, 12),   # 立夏 → 阳遁
        (2025, 7, 15, 12),   # 小暑 → 阴遁
        (2025, 10, 10, 12),  # 寒露 → 阴遁
        (2025, 12, 28, 12),  # 冬至 → 阳遁
        (2026, 2, 14, 12),   # 立春 → 阳遁
    ]
    for y, m, d, h in cases:
        got = compute_qimen(y, m, d, h)["type"]
        exp = _oracle_dingju(y, m, d, h)
        assert got == exp, f"{y}-{m}-{d} 定局 {got} != oracle {exp}"


def _oracle_zhifu(year: int, month: int, day: int, hour: int,
                  yinyang: str, ju_num: int):
    """独立 oracle：复算值符星/值使门（给定手动局数）。"""
    seq = [1, 2, 3, 4, 5, 6, 7, 8, 9] if yinyang == "阳" else [1, 9, 8, 7, 6, 5, 4, 3, 2]
    start = seq.index(ju_num)
    dipan = {q: seq[(start + i) % 9] for i, q in enumerate(QIYI_SEQ)}
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lunar = solar.getLunar()
    tg = lunar.getTimeInGanZhi()
    ti = _gz_index(tg[0], tg[1])
    txun = ti - ti % 10
    qy = XUNSHOU_QIYI[txun]
    gong0 = dipan[qy]
    return f"{PALACE_STAR[gong0]}星", PALACE_DOOR.get(gong0, "死门")


def test_valuefu_valueshi():
    """值符值使：应以时柱旬首奇仪落宫之星/门为准（与独立 oracle 一致）。"""
    cases = [
        (2025, 3, 10, 0, "阳", 1),   # 甲子时附近 → 戊落坎 → 天蓬/休门
        (2025, 3, 10, 12, "阴", 9),
        (2025, 7, 15, 6, "阳", 4),
        (2025, 7, 15, 18, "阴", 6),
    ]
    for y, m, d, h, yy, ju in cases:
        r = compute_qimen(y, m, d, h, manual_ju=(yy, ju))
        exp_star, exp_door = _oracle_zhifu(y, m, d, h, yy, ju)
        assert r["valueFu"] == exp_star, (r["valueFu"], exp_star)
        assert r["valueShi"] == exp_door, (r["valueShi"], exp_door)


def test_tianpan_coverage():
    """天盘九星：九宫每宫一星，九星不重不漏（含中五寄天禽）。"""
    for yy, ju in [("阳", 1), ("阴", 9), ("阳", 4), ("阴", 6)]:
        r = compute_qimen(2025, 3, 10, 12, manual_ju=(yy, ju))
        stars = [p["star"] for p in r["palaces"]]
        assert sorted(stars) == sorted(PALACE_STAR.values()), (yy, ju, stars)
