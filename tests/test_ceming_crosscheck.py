"""测字 / 姓名五格 / 合婚 —— oracle 交叉校验（P2-2）。

两路校验（与奇门 / 八字 / 梅花 crosscheck 同一范式）：
  (a) 对照典籍常量表，抓字面笔误（六合 / 六冲 / 六害 / 三合 / 三刑 / 天干五合 / 81 数理表）；
  (b) 不调用被测函数，用独立实现复算关键字段（五格用硬编码手算值，测字用码点重算）。
"""

from __future__ import annotations

import pytest

from app.services.paipan.ceming import (
    DIZHI,
    GAN_HE,
    LIU_CHONG,
    LIU_HAI,
    LIU_HE,
    NUM_81,
    SAN_HE,
    SAN_XING,
    SHENG,
    TAIL_WUXING,
    TRIGRAMS,
    ZODIAC,
    compute_cezi,
    compute_hehun,
    compute_wuge,
    tail_wuxing,
    wrap81,
)

# ===== (a) 常量表对照 =====

# 地支六合：子丑合土、寅亥合木、卯戌合火、辰酉合金、巳申合水、午未合日月
EXPECT_LIU_HE = {("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")}
# 地支六冲（隔六位）：子午、丑未、寅申、卯酉、辰戌、巳亥
EXPECT_LIU_CHONG = {("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")}
# 地支六害（穿）：子未、丑午、寅巳、卯辰、申亥、酉戌
EXPECT_LIU_HAI = {("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")}
# 三合局：申子辰水、亥卯未木、寅午戌火、巳酉丑金
EXPECT_SAN_HE = {("申", "子", "辰"), ("亥", "卯", "未"), ("寅", "午", "戌"), ("巳", "酉", "丑")}
# 三刑：寅巳申无恩之刑、丑未戌恃势之刑、子卯无礼之刑
EXPECT_SAN_XING = {("寅", "巳", "申"), ("丑", "未", "戌"), ("子", "卯")}
# 天干五合：甲己合土、乙庚合金、丙辛合水、丁壬合木、戊癸合火
EXPECT_GAN_HE = {("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸")}


def _as_set(pairs):
    return {tuple(p) for p in pairs}


def test_dizhi_and_zodiac_order():
    assert DIZHI == list("子丑寅卯辰巳午未申酉戌亥")
    assert ZODIAC == list("鼠牛虎兔龙蛇马羊猴鸡狗猪")
    assert len(DIZHI) == len(ZODIAC) == 12
    # 生肖与地支一一对应（子鼠、丑牛 …）
    assert ZODIAC[DIZHI.index("午")] == "马"
    assert ZODIAC[DIZHI.index("酉")] == "鸡"


def test_relation_tables_vs_classic():
    assert _as_set(LIU_HE) == EXPECT_LIU_HE
    assert _as_set(LIU_CHONG) == EXPECT_LIU_CHONG
    assert _as_set(LIU_HAI) == EXPECT_LIU_HAI
    assert _as_set(SAN_HE) == EXPECT_SAN_HE
    assert _as_set(SAN_XING) == EXPECT_SAN_XING
    assert _as_set(GAN_HE) == EXPECT_GAN_HE


def test_81_table_integrity():
    """81 数理必须 1..81 全覆盖，且吉凶值域合法。"""
    assert sorted(NUM_81) == list(range(1, 82))
    legal = {"大吉", "吉", "半吉", "凶", "大凶"}
    for n, info in NUM_81.items():
        assert info["ji"] in legal, f"{n} 吉凶值非法：{info['ji']}"
        assert info["mean"], f"{n} 缺简释"
    # 几个公认的大吉数：1 太极、5 福寿、11 旱苗逢雨、21 明月中天、24 金钱丰盈
    for n in (1, 5, 11, 21, 24, 31, 33, 45, 65, 81):
        assert NUM_81[n]["ji"] == "大吉", f"{n} 应为大吉"
    # 公认的凶数：2 一身孤节、4 破败凶变、9 破舟入海、10 万事终局
    for n in (2, 4, 9, 10, 19, 20, 34, 44):
        assert NUM_81[n]["ji"] == "凶", f"{n} 应为凶"


def test_tail_wuxing_mapping():
    """尾数 → 五行：1,2 木 / 3,4 火 / 5,6 土 / 7,8 金 / 9,0 水。"""
    expect = {1: "木", 2: "木", 3: "火", 4: "火", 5: "土",
              6: "土", 7: "金", 8: "金", 9: "水", 0: "水"}
    assert TAIL_WUXING == expect
    for k, v in expect.items():
        assert tail_wuxing(k) == v
    assert tail_wuxing(15) == "土"   # 尾 5
    assert tail_wuxing(28) == "金"   # 尾 8
    assert tail_wuxing(30) == "水"   # 尾 0


def test_wrap81_cycle():
    assert wrap81(1) == 1
    assert wrap81(81) == 81
    assert wrap81(82) == 1
    assert wrap81(162) == 81
    assert wrap81(0) == 1
    assert wrap81(-5) == 1


# ===== (b) 五格：硬编码手算值独立复算 =====

# 五格规则：天 = 单姓+1 / 复姓之和；人 = 姓末 + 名首；地 = 名之和（单名 +1）；总 = 全和；外 = 总 − 人 + 1
# 下列期望值均为手算结果，作为独立 oracle 校验（不复用被测函数的实现）
@pytest.mark.parametrize("s,g,tian,ren,di,wai,zong", [
    ([4], [11], 5, 15, 12, 1, 15),
    ([4], [11, 6], 5, 15, 17, 7, 21),
    ([15, 6], [11, 6], 21, 17, 17, 22, 38),
    ([7], [5], 8, 12, 6, 1, 12),
])
def test_wuge_known_cases(s, g, tian, ren, di, wai, zong):
    res = compute_wuge(s, g)
    gr = res["grids"]
    assert gr["tian"]["num"] == tian
    assert gr["ren"]["num"] == ren
    assert gr["di"]["num"] == di
    assert gr["wai"]["num"] == wai
    assert gr["zong"]["num"] == zong
    # 数理 k 必须是 81 取模后的值
    for key in ("tian", "ren", "di", "wai", "zong"):
        assert gr[key]["k"] == wrap81(gr[key]["num"])
        assert 1 <= gr[key]["k"] <= 81


def test_three_talent_wuxing():
    """三才 = 天/人/地 三格的尾数五行。"""
    res = compute_wuge([4], [11, 6])  # 天 5 / 人 15 / 地 17
    tt = res["threeTalent"]
    assert tt["tian"] == tail_wuxing(5) == "土"
    assert tt["ren"] == tail_wuxing(15) == "土"
    assert tt["di"] == tail_wuxing(17) == "金"
    assert tt["text"]


def test_wuge_score_bounds_and_validation():
    for s, g in (([4], [11]), ([4], [11, 6]), ([15, 6], [11, 6])):
        r = compute_wuge(s, g)
        assert 0 <= r["score"] <= 100
    with pytest.raises(ValueError):
        compute_wuge([], [11])
    with pytest.raises(ValueError):
        compute_wuge([4], [])


def test_wuge_incomplete_flag():
    """笔画缺失（<=0）必须标记 incomplete，避免给用户一个看似完整的结果。"""
    assert compute_wuge([4], [11])["incomplete"] is False
    assert compute_wuge([4], [0])["incomplete"] is True


# ===== (b) 合婚：独立判定期望 =====

@pytest.mark.parametrize("m,f,expect_verdict,expect_level", [
    ("子", "丑", "生肖六合", "上吉"),
    ("午", "未", "生肖六合", "上吉"),
    ("子", "午", "生肖六冲", "凶"),
    ("寅", "申", "生肖六冲", "凶"),
    ("子", "未", "生肖六害", "凶"),
    # 寅巳 同时命中「六害」与「三刑」，实现里六害优先级更高
    ("寅", "巳", "生肖六害", "凶"),
    # 子卯 为纯无礼之刑（不落在六合/三合/六冲/六害中）
    ("子", "卯", "生肖相刑", "凶"),
    ("申", "辰", "生肖三合", "吉"),
    ("子", "寅", "生肖无刑冲合害", "平"),
])
def test_hehun_verdict(m, f, expect_verdict, expect_level):
    r = compute_hehun(m, f)
    assert r["verdict"] == expect_verdict
    assert r["level"] == expect_level
    assert r["maleZodiac"] == ZODIAC[DIZHI.index(m)]
    assert r["femaleZodiac"] == ZODIAC[DIZHI.index(f)]


def test_hehun_relations_flags():
    r = compute_hehun("子", "丑")
    assert r["relations"]["he"] is True
    assert r["relations"]["chong"] is False
    r2 = compute_hehun("子", "午")
    assert r2["relations"]["chong"] is True
    assert r2["relations"]["he"] is False


def test_hehun_ganhe_and_complement():
    r = compute_hehun("子", "丑", male_gan="甲", female_gan="己")
    assert r["relations"]["ganHe"] is True
    # 双方都缺金 → missingBoth 应含金，且分数被扣
    r2 = compute_hehun(
        "子", "丑",
        male_wuxing={"木": 2, "火": 1, "土": 0, "金": 0, "水": 1},
        female_wuxing={"木": 1, "火": 2, "土": 0, "金": 0, "水": 1},
    )
    assert "金" in r2["missingBoth"]
    assert r2["score"] < r["score"]


def test_hehun_validation():
    with pytest.raises(ValueError):
        compute_hehun("猫", "午")


# ===== (b) 测字：码点独立复算 =====

@pytest.mark.parametrize("ch", ["梦", "龙", "安", "心", "道", "水"])
def test_cezi_deterministic(ch):
    code = ord(ch)
    r = compute_cezi(ch, strokes=10)
    # oracle：不调用被测函数，直接按码点重算
    assert r["element"] == SHENG[code % 5]
    assert r["trigram"]["name"] == TRIGRAMS[(code >> 2) % 8][0]
    assert r["codePoint"] == code
    assert r["strokes"] == 10
    assert r["tendency"]


def test_cezi_validation():
    with pytest.raises(ValueError):
        compute_cezi("")
