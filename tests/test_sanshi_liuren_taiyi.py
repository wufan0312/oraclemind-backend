"""三式补齐 —— 大六壬 / 太乙神数 起例校验与端到端回归（P2-1 / P2-2）。

校验口径（与既有 qimen / bazi / ceming crosscheck 同一范式）：
  (a) 常量表对照典籍起例（月将 / 寄宫 / 贵人 / 十六宫神 / 九宫八卦）；
  (b) 不调用被测函数，用独立实现复算关键字段（天地盘、四课、三传递推、积年、行宫）；
  (c) 不变量：天盘是十二支的排列、三传中末传递推、中五不居、局序在 1~72；
  (d) 端点 200 + 缓存一致性。

注意：大六壬 / 太乙流派差异大，本套测试校验的是**本实现内部自洽与起例表正确**，
不声称与外部某一典籍完全一致（太乙的 provenance 字段已显式声明所采之说）。
"""

from __future__ import annotations

import pytest

from app.services.paipan.liuren import (
    BA_ZHUAN_RI,
    GAN_HE,
    GAN_JI_GONG,
    GUI_REN,
    JIANG_SHUN_ZHI,
    TIAN_JIANG,
    YI_MA,
    YUE_JIANG_BY_JIEQI,
    ZHI,
    _hour_to_zhi,
    _liuqin,
    _san_chuan_recur,
    _xun_gan_table,
    _zhi_add,
    compute_liuren,
)
from app.services.paipan.taiyi import (
    GONG_9,
    JINIAN_BASE,
    JINIAN_BASE_YEAR,
    LIU_HE_16,
    RING_16,
    SHEN_16,
    TAIYI_SEQ,
    YANG_GONG,
    YIN_GONG,
    compute_taiyi,
)


# ==================================================================
# 大六壬
# ==================================================================

# ===== (a) 起例常量表 =====

# 月将（太阳过宫）：雨水亥、春分戌、谷雨酉、小满申、夏至未、大暑午、
# 处暑巳、秋分辰、霜降卯、小雪寅、冬至丑、大寒子
EXPECT_YUE_JIANG_ZHI = {
    "雨水": "亥", "春分": "戌", "谷雨": "酉", "小满": "申",
    "夏至": "未", "大暑": "午", "处暑": "巳", "秋分": "辰",
    "霜降": "卯", "小雪": "寅", "冬至": "丑", "大寒": "子",
}
# 日干寄宫：甲寅 乙辰 丙巳 丁未 戊巳 己未 庚申 辛戌 壬亥 癸丑
EXPECT_JI_GONG = {"甲": "寅", "乙": "辰", "丙": "巳", "丁": "未", "戊": "巳",
                  "己": "未", "庚": "申", "辛": "戌", "壬": "亥", "癸": "丑"}
# 贵人口诀（阳贵在前、阴贵在后）：甲戊庚牛羊 / 乙己鼠猴 / 丙丁猪鸡 / 壬癸兔蛇 / 六辛马虎
EXPECT_GUI_REN = {"甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
                  "乙": ("子", "申"), "己": ("子", "申"),
                  "丙": ("亥", "酉"), "丁": ("亥", "酉"),
                  "壬": ("卯", "巳"), "癸": ("卯", "巳"),
                  "辛": ("午", "寅")}
# 十二天将序
EXPECT_TIAN_JIANG = ["贵人", "腾蛇", "朱雀", "六合", "勾陈", "青龙",
                     "天空", "白虎", "太常", "玄武", "太阴", "天后"]


def test_yue_jiang_table():
    for jq, zhi in EXPECT_YUE_JIANG_ZHI.items():
        assert YUE_JIANG_BY_JIEQI[jq][0] == zhi, jq
    # 十二将名不重复
    names = {v[1] for v in YUE_JIANG_BY_JIEQI.values()}
    assert len(names) == 12


def test_ji_gong_and_gui_ren_tables():
    assert GAN_JI_GONG == EXPECT_JI_GONG
    assert GUI_REN == EXPECT_GUI_REN


def test_tian_jiang_order_and_coverage():
    assert TIAN_JIANG == EXPECT_TIAN_JIANG
    assert len(set(TIAN_JIANG)) == 12
    # 贵人顺逆的六个方位 + 其余六个，恰好覆盖十二支（顺逆各半）
    others = set(ZHI) - JIANG_SHUN_ZHI
    assert len(JIANG_SHUN_ZHI) == 6 and len(others) == 6


def test_yi_ma_table():
    """驿马：申子辰马在寅 / 寅午戌马在申 / 巳酉丑马在亥 / 亥卯未马在巳"""
    for z in ("申", "子", "辰"):
        assert YI_MA[z] == "寅"
    for z in ("寅", "午", "戌"):
        assert YI_MA[z] == "申"
    for z in ("巳", "酉", "丑"):
        assert YI_MA[z] == "亥"
    for z in ("亥", "卯", "未"):
        assert YI_MA[z] == "巳"


# ===== (b) 独立复算 =====

@pytest.mark.parametrize(
    "hour,zhi",
    # 时辰区间 [start, end)：子 23-1 / 丑 1-3 / 寅 3-5 / 卯 5-7 / 辰 7-9 / 巳 9-11
    #                       / 午 11-13 / 未 13-15 / 申 15-17 / 酉 17-19 / 戌 19-21 / 亥 21-23
    [(23, "子"), (0, "子"), (1, "丑"), (2, "丑"), (11, "午"), (12, "午"),
     (13, "未"), (22, "亥")],
)
def test_hour_to_zhi(hour, zhi):
    assert _hour_to_zhi(hour) == zhi


@pytest.mark.parametrize(
    "ri_gan,ri_zhi,expect_first,expect_kong",
    [
        ("甲", "子", ("子", "甲"), ["戌", "亥"]),   # 甲子旬，戌亥空
        ("甲", "戌", ("戌", "甲"), ["申", "酉"]),   # 甲戌旬，申酉空
        ("甲", "申", ("申", "甲"), ["午", "未"]),
        ("甲", "午", ("午", "甲"), ["辰", "巳"]),
        ("甲", "辰", ("辰", "甲"), ["寅", "卯"]),
        ("甲", "寅", ("寅", "甲"), ["子", "丑"]),
    ],
)
def test_xun_gan_table(ri_gan, ri_zhi, expect_first, expect_kong):
    table, kong = _xun_gan_table(ri_gan, ri_zhi)
    assert table[expect_first[0]] == expect_first[1]
    assert sorted(kong) == sorted(expect_kong)
    assert len(table) == 10          # 每旬恰好十干配十支
    assert len(set(table.values())) == 10
    # 空亡两支不在旬干表内
    assert all(z not in table for z in kong)


@pytest.mark.parametrize(
    "day_gan,other,expect",
    [("甲", "甲", "比肩"), ("甲", "乙", "比肩"),   # 同五行
     ("甲", "壬", "父母"), ("甲", "癸", "父母"),   # 水生木，生我
     ("甲", "丙", "子孙"),                          # 木生火，我生
     ("甲", "庚", "官鬼"),                          # 金克木，克我
     ("甲", "戊", "妻财")],                         # 木克土，我克
)
def test_liuqin(day_gan, other, expect):
    assert _liuqin(day_gan, other) == expect


def test_gan_he_is_involution():
    """天干五合是相互的。"""
    for a, b in GAN_HE.items():
        assert GAN_HE[b] == a


# ===== (c) 排盘不变量 =====

def _drain(year, month, day, hour, time_text=""):
    return compute_liuren(year, month, day, hour, "男", time_text, "")


@pytest.mark.parametrize(
    "ymd_h",
    [(1990, 6, 21, 14), (2026, 9, 10, 8), (2000, 1, 1, 0), (2010, 12, 31, 23), (1985, 3, 15, 20)],
)
def test_liuren_invariants(ymd_h):
    r = _drain(*ymd_h)
    # 天盘是十二支的一个排列（双射）
    shen_list = [p["shen"] for p in r["tianPan"]]
    assert sorted(shen_list) == sorted(ZHI)
    # 月将加占时：天盘在「占时」位上的神 = 月将
    pan_by_zhi = {p["zhi"]: p["shen"] for p in r["tianPan"]}
    assert pan_by_zhi[r["zhanShi"]] == r["yueJiang"]
    # 四课：干上神 = 天盘在寄宫上的神
    assert r["siKe"][0]["upper"] == pan_by_zhi[r["jiGong"]]
    assert r["siKe"][1]["lower"] == r["siKe"][0]["upper"]
    assert r["siKe"][1]["upper"] == pan_by_zhi[r["siKe"][0]["upper"]]
    assert r["siKe"][2]["upper"] == pan_by_zhi[r["riZhi"]]
    assert r["siKe"][3]["lower"] == r["siKe"][2]["upper"]
    # 空亡恰好两支
    assert len(r["kongWang"]) == 2
    # 十二天将覆盖十二支
    assert sorted(t["zhi"] for t in r["tianJiang"]) == sorted(ZHI)
    assert sorted(t["jiang"] for t in r["tianJiang"]) == sorted(TIAN_JIANG)
    # 三传三项齐全
    assert len(r["sanChuan"]["items"]) == 3


# 这几个课体的中末传是「别取」而非天盘递推，不适用递推不变量
NON_RECURRENT = ("昴星", "别责", "八专", "伏吟", "反吟")


def test_san_chuan_recurrence_holds_for_recurrent_methods():
    """中传 = 天盘加临初传之神，末传 = 天盘加临中传之神。

    仅对「初传由四课克贼 / 遥克取得」的课体成立；昴星、别责、八专、伏吟、反吟
    各有别取之法（初传不由克贼定，中末传多直接归干支上神），故跳过。
    """
    checked = 0
    for h in range(24):
        r = _drain(2026, 9, 10, h)
        if any(tag in r["sanChuan"]["method"] for tag in NON_RECURRENT):
            continue
        if r["fuYin"] or r["fanYin"]:
            continue
        pan = {p["zhi"]: p["shen"] for p in r["tianPan"]}
        chu = r["sanChuan"]["chu"]
        assert r["sanChuan"]["zhong"] == pan[chu], (h, r["sanChuan"])
        assert r["sanChuan"]["mo"] == pan[r["sanChuan"]["zhong"]], (h, r["sanChuan"])
        checked += 1
    assert checked > 0, "没有覆盖到任何递推课体，用例失效"


def test_fuyin_detected_when_yuejiang_equals_zhanshi():
    """月将临占时 → 伏吟（天地盘同位）。"""
    r = _drain(1990, 6, 21, 14)          # 夏至后未将，14 时 = 未时
    assert r["yueJiang"] == r["zhanShi"] == "未"
    assert r["fuYin"] is True
    assert r["fanYin"] is False
    # 伏吟时天地盘同位
    for p in r["tianPan"]:
        assert p["shen"] == p["zhi"]


def test_bazhuan_day_constant():
    """八专日清单（典籍固定条目：甲寅 乙卯 丁未 己未 庚申 辛酉 癸丑）。

    注意：其中只有「日干寄宫 == 日支」的那些日子才真正出现「四课止二课」的八专课
    （乙寄辰、辛寄戌，与卯/酉不同位，故 乙卯 / 辛酉 在此寄宫表下仍为四课）。
    本实现按 dedup 后的实际课数判定，不靠名单硬套，见 test_liuren_invariants。
    """
    assert BA_ZHUAN_RI == {("甲", "寅"), ("乙", "卯"), ("丁", "未"), ("己", "未"),
                           ("庚", "申"), ("辛", "酉"), ("癸", "丑")}
    same_gong = {(g, z) for g, z in BA_ZHUAN_RI if GAN_JI_GONG[g] == z}
    assert same_gong == {("甲", "寅"), ("丁", "未"), ("己", "未"), ("庚", "申"), ("癸", "丑")}


def test_zhi_add_wraps():
    assert _zhi_add("子", 0) == "子"
    assert _zhi_add("子", 12) == "子"
    assert _zhi_add("子", -1) == "亥"
    assert _zhi_add("亥", 1) == "子"


def test_san_chuan_recur_helper():
    tian = {z: _zhi_add(z, 1) for z in ZHI}   # 天盘整体顺移一位
    zhong, mo = _san_chuan_recur(tian, "子")
    assert zhong == "丑" and mo == "寅"


# ==================================================================
# 太乙神数
# ==================================================================

# ===== (a) 起例常量表 =====

def test_ring16_and_shen16():
    assert len(RING_16) == 16
    assert len(set(RING_16)) == 16
    assert set(SHEN_16) == set(RING_16)
    # 十六宫 = 十二地支 + 四维
    assert set(RING_16) - set(ZHI) == {"乾", "坤", "艮", "巽"}


def test_shen16_names():
    """十六宫神名（各本一致）。"""
    expect = {"子": "地主", "丑": "阳德", "艮": "和德", "寅": "吕申",
              "卯": "高丛", "辰": "太阳", "巽": "大灵", "巳": "大神",
              "午": "大威", "未": "天道", "坤": "大武", "申": "武德",
              "酉": "太簇", "戌": "阴主", "乾": "阴德", "亥": "大义"}
    assert SHEN_16 == expect


def test_gong9_no_zhongwu_and_covers_eight():
    """太乙行八卦，不入中五。"""
    assert 5 not in GONG_9
    assert sorted(GONG_9) == [1, 2, 3, 4, 6, 7, 8, 9]
    assert TAIYI_SEQ == [1, 2, 3, 4, 6, 7, 8, 9]
    # 阳遁宫 + 阴遁宫 恰好分完八卦
    assert YANG_GONG | YIN_GONG == set(GONG_9)
    assert not (YANG_GONG & YIN_GONG)


def test_liuhe16_is_involution():
    for a, b in LIU_HE_16.items():
        assert LIU_HE_16[b] == a


# ===== (b) 独立复算 =====

@pytest.mark.parametrize("year", [1984, 1990, 2000, 2026, 2100])
def test_jinian_formula(year):
    r = compute_taiyi(year, 6, 1, 12)
    assert r["jiNian"] == JINIAN_BASE + (year - JINIAN_BASE_YEAR)
    assert 1 <= r["ju"] <= 72


def test_taiyi_gong_three_year_shift():
    """三年一徙宫：同一 3 年块内宫位不变，跨块后按行宫序推进一位。"""
    def gong_of(y):
        return compute_taiyi(y, 6, 1, 12)["taiYiGong"]["gong"]

    base_year = JINIAN_BASE_YEAR + 3 * 5       # 取第 5 块的起始年
    g0 = gong_of(base_year)
    assert gong_of(base_year + 1) == g0
    assert gong_of(base_year + 2) == g0
    # 跨一块 → 行宫序推进一位
    idx = TAIYI_SEQ.index(g0)
    assert gong_of(base_year + 3) == TAIYI_SEQ[(idx + 1) % 8]


# ===== (c) 排盘不变量 =====

@pytest.mark.parametrize("year", [1984, 1990, 2000, 2012, 2026, 2044])
def test_taiyi_invariants(year):
    r = compute_taiyi(year, 6, 1, 12)
    # 中五不居
    for key in ("taiYiGong", "zhuDaJiang", "keDaJiang", "zhuCanJiang", "keCanJiang"):
        assert r[key]["gong"] != 5, key
    # 十六宫齐全且神名正确
    assert len(r["shiLiuGong"]) == 16
    assert [g["pos"] for g in r["shiLiuGong"]] == RING_16
    assert all(g["shen"] == SHEN_16[g["pos"]] for g in r["shiLiuGong"])
    # 恰有一位是太乙本位
    assert sum(1 for g in r["shiLiuGong"] if g["isTaiYi"]) == 1
    # 主客算在 1~16
    assert 1 <= r["zhuSuan"] <= 16
    assert 1 <= r["keSuan"] <= 16
    # 阴阳遁与宫位自洽
    assert r["yangDun"] == (r["taiYiGong"]["gong"] in YANG_GONG)
    assert r["dun"] == ("阳遁" if r["yangDun"] else "阴遁")
    # 局序/小周范围
    assert 1 <= r["xiaoZhou"] <= 24
    # provenance 必须存在（流派声明，前端据此后撤权威措辞）
    assert "provenance" in r and len(r["provenance"]) > 20


# ==================================================================
# 端到端：路由
# ==================================================================

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


BASE_REQ = {"year": 1990, "month": 6, "day": 21, "hour": 14, "gender": "男"}


@pytest.mark.parametrize("path,keys", [
    ("/api/v1/liuren/paipan", ["yueJiang", "siKe", "sanChuan", "tianPan", "tianJiang"]),
    ("/api/v1/taiyi/paipan", ["jiNian", "taiYiGong", "zhuSuan", "shiLiuGong"]),
])
def test_endpoints_ok(client, path, keys):
    r = client.post(path, json=BASE_REQ)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in keys:
        assert k in body, k


def test_liuren_endpoint_accepts_time_text_only(client):
    r = client.post("/api/v1/liuren/paipan",
                    json={"year": 1990, "month": 6, "day": 21, "timeText": "午时", "gender": "男"})
    assert r.status_code == 200
    assert r.json()["sanChuan"]["items"]


def test_taiyi_endpoint_rejects_bad_year(client):
    assert client.post("/api/v1/taiyi/paipan",
                       json={**BASE_REQ, "year": 1800}).status_code == 422


def test_cache_stability(client):
    """同参数两次请求结果一致。"""
    for path in ("/api/v1/liuren/paipan", "/api/v1/taiyi/paipan"):
        a = client.post(path, json=BASE_REQ).json()
        b = client.post(path, json=BASE_REQ).json()
        assert a == b
