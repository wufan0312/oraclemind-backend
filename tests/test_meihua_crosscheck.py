# -*- coding: utf-8 -*-
"""梅花易数排盘 · 权威盘 cross-check（对齐 test_qimen_crosscheck 模式）。

两路校验：
1. 对照典籍的常量表（先天八卦数 乾1兑2…坤8）—— 抓字面笔误。
2. 不调用 compute_meihua，改用 lunar-python 原语独立复算「起卦算术」
   （年支数+月+日 / +时支数 → %8 / %6），并独立推导体用规则与体用生克，
   与被测输出逐字段比对 —— 抓"接线"类 bug。

覆盖四种起卦法（时间 / 数字 / 字数 / 手动）。
"""
from lunar_python import Solar

from app.services.paipan.meihua import compute_meihua
from app.services.paipan.yijing_data import NUM_TRIGRAM, TRIGRAM_NUM, TRIGRAM_WUXING

# 地支序数（梅花起卦用）：子1…亥12（独立复算用，不从被测代码导入）
ZHI_ORD = {"子": 1, "丑": 2, "寅": 3, "卯": 4, "辰": 5, "巳": 6,
           "午": 7, "未": 8, "申": 9, "酉": 10, "戌": 11, "亥": 12}

# ===== 1) 先天八卦数表对照典籍 =====
EXPECT_TRIGRAM_NUM = {"乾": 1, "兑": 2, "离": 3, "震": 4,
                      "巽": 5, "坎": 6, "艮": 7, "坤": 8}


def test_trigram_num_table():
    """先天八卦数：乾1兑2离3震4巽5坎6艮7坤8，且 NUM_TRIGRAM 为其逆映射。"""
    assert TRIGRAM_NUM == EXPECT_TRIGRAM_NUM, TRIGRAM_NUM
    inv = {v: k for k, v in NUM_TRIGRAM.items()}
    assert inv == EXPECT_TRIGRAM_NUM, inv


# ===== 独立复算原语 =====
def _oracle_qigua_time(year: int, month: int, day: int, hour: int):
    """时间起卦：上=(年支数+月+日)%8、下=+时支数%8、动=+时支数%6。"""
    lunar = Solar.fromYmdHms(year, month, day, hour, 0, 0).getLunar()
    y_z = ZHI_ORD[lunar.getYearZhi()]
    m, d = lunar.getMonth(), lunar.getDay()
    t_z = ZHI_ORD[lunar.getTimeZhi()]
    total = y_z + m + d
    return total % 8 or 8, (total + t_z) % 8 or 8, (total + t_z) % 6 or 6


def _oracle_tiyong(shang_gua: str, xia_gua: str, dong: int):
    """体用规则：动爻在下卦(1-3)→体上用下；在上卦(4-6)→体下用上。"""
    if dong <= 3:
        return shang_gua, xia_gua
    return xia_gua, shang_gua


def _oracle_shengke(ti_wx: str, yong_wx: str):
    """体用生克 → (关系, 吉凶)（经典定义，独立实现）。"""
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if sheng.get(yong_wx) == ti_wx:
        return "用生体", "吉"
    if yong_wx == ti_wx:
        return "比和", "吉"
    if ke.get(ti_wx) == yong_wx:
        return "体克用", "小吉"
    if sheng.get(ti_wx) == yong_wx:
        return "体生用", "小凶"
    return "用克体", "凶"


def test_time_qigua_and_trigrams():
    """时间起卦：上/下卦数与动爻须与独立复算一致，并正确映射为卦名。"""
    cases = [(2024, 12, 25, 12), (2025, 3, 10, 0), (1987, 6, 12, 12),
             (2000, 2, 29, 6), (1995, 11, 23, 18)]
    for y, m, d, h in cases:
        r = compute_meihua(y, m, d, h, "男", method="time")
        shang, xia, dong = _oracle_qigua_time(y, m, d, h)
        assert r["benGua"]["upper"]["name"] == NUM_TRIGRAM[shang], (y, m, d, r["benGua"]["upper"]["name"], NUM_TRIGRAM[shang])
        assert r["benGua"]["lower"]["name"] == NUM_TRIGRAM[xia], (y, m, d, r["benGua"]["lower"]["name"], NUM_TRIGRAM[xia])
        assert r["dongYao"] == dong, (y, m, d, r["dongYao"], dong)
        assert r["method"] == "time"


def test_time_tiyong_and_shengke():
    """体用卦与体用生克须与独立推导一致。"""
    cases = [(2024, 12, 25, 12), (2025, 3, 10, 0), (1987, 6, 12, 12),
             (2000, 2, 29, 6), (1995, 11, 23, 18)]
    for y, m, d, h in cases:
        r = compute_meihua(y, m, d, h, "男", method="time")
        shang, xia, dong = _oracle_qigua_time(y, m, d, h)
        shang_gua, xia_gua = NUM_TRIGRAM[shang], NUM_TRIGRAM[xia]
        ti, yong = _oracle_tiyong(shang_gua, xia_gua, dong)
        assert r["ti"]["name"] == ti, (y, m, d, r["ti"]["name"], ti)
        assert r["yong"]["name"] == yong, (y, m, d, r["yong"]["name"], yong)
        rel, ji = _oracle_shengke(TRIGRAM_WUXING[ti], TRIGRAM_WUXING[yong])
        assert r["tiYong"]["relation"] == rel, (y, m, d, r["tiYong"]["relation"], rel)
        assert r["tiYong"]["rawJi"] == ji, (y, m, d, r["tiYong"]["rawJi"], ji)
        # 未因旺衰修正时，ji 须等于 rawJi
        if not r["tiYong"]["jiAdjusted"]:
            assert r["tiYong"]["ji"] == ji


def test_number_qigua():
    """数字起卦：上=num1%8、下=num2%8、动=(num1+num2)%6。"""
    r = compute_meihua(2024, 1, 1, 12, "男", method="number", num1=15, num2=23)
    shang = 15 % 8 or 8
    xia = 23 % 8 or 8
    dong = (15 + 23) % 6 or 6
    assert r["benGua"]["upper"]["name"] == NUM_TRIGRAM[shang]
    assert r["benGua"]["lower"]["name"] == NUM_TRIGRAM[xia]
    assert r["dongYao"] == dong
    assert r["method"] == "number"


def test_text_qigua():
    """字数起卦：前/后段字数取上下卦，总字数取动爻。"""
    q = "今日宜出行否"
    r = compute_meihua(2024, 1, 1, 12, "男", method="text", question=q)
    n = len(q)
    half = n // 2
    a = half if half else 1
    b = n - half if (n - half) else 1
    shang = a % 8 or 8
    xia = b % 8 or 8
    dong = n % 6 or 6
    assert r["benGua"]["upper"]["name"] == NUM_TRIGRAM[shang]
    assert r["benGua"]["lower"]["name"] == NUM_TRIGRAM[xia]
    assert r["dongYao"] == dong
    assert r["method"] == "text"


def test_manual_qigua():
    """手动指定：直接取上/下卦数与动爻（1-8,1-8,1-6）。"""
    r = compute_meihua(2024, 1, 1, 12, "男", method="manual",
                       shang_num=1, xia_num=2, dong_num=3)
    assert r["benGua"]["upper"]["name"] == NUM_TRIGRAM[1]
    assert r["benGua"]["lower"]["name"] == NUM_TRIGRAM[2]
    assert r["dongYao"] == 3
    assert r["ti"]["name"] == NUM_TRIGRAM[1]  # 动爻3<=3 → 体上
    assert r["yong"]["name"] == NUM_TRIGRAM[2]


def test_hexagram_structure():
    """本/变/互/错/综 五卦结构完整，变卦必异于本卦。"""
    r = compute_meihua(2024, 12, 25, 12, "男", method="time")
    assert r["benGua"] and r["benGua"]["name"]
    assert r["bianGua"] and r["bianGua"]["name"] != r["benGua"]["name"]
    assert r["huGua"] and r["huGua"]["name"]
    assert r["cuoGua"] and r["cuoGua"]["name"]
    assert r["zongGua"] and r["zongGua"]["name"]


def test_manual_tiyong_upper_dong():
    """动爻在上卦(4-6)时体用翻转：体=下卦、用=上卦。"""
    r = compute_meihua(2024, 1, 1, 12, "男", method="manual",
                       shang_num=3, xia_num=4, dong_num=5)
    assert r["ti"]["name"] == NUM_TRIGRAM[4]   # 动爻5>3 → 体下
    assert r["yong"]["name"] == NUM_TRIGRAM[3]
