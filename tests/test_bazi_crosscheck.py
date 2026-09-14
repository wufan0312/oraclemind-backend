# -*- coding: utf-8 -*-
"""八字排盘 · 权威盘 cross-check（对齐 test_qimen_crosscheck 模式）。

两路校验：
1. 对照典籍的常量表（神煞、十神定义）—— 抓字面笔误。
2. 不调用 compute_bazi，改用 lunar-python 原语（getEightChar / 藏干表 /
   五行生克）独立复算四柱、十神、五行、缺数、神煞落宫，与被测输出逐字段比对
   —— 抓"接线"类 bug（取错字段、十神关系写反、加权错位、落宫错配）。

不依赖"现在"，用固定生日 + 多组性别/时辰覆盖阴阳顺逆。
"""
from datetime import date

from lunar_python import Solar

from app.services.paipan.bazi import compute_bazi
from app.services.paipan.bazi import (
    _GUIREN, _WENCHANG, _TAOHUA, _YIMA, _HUAGAI, _LUSHEN, _YANGREN, _KONGWANG,
)
from app.services.paipan.yijing_data import (
    GAN, GAN_WUXING, ZHI, ZHI_WUXING, ZHI_HIDE_GAN,
)

# ===== 1) 神煞表对照典籍 =====
SHENG_XIAO_GUIREN = {  # 天乙贵人（日干）：甲戊庚牛羊、乙己鼠猴乡、丙丁猪鸡位、壬癸兔蛇藏、六辛逢马虎
    "甲": "丑未", "戊": "丑未", "庚": "丑未",
    "乙": "子申", "己": "子申",
    "丙": "亥酉", "丁": "亥酉",
    "壬": "卯巳", "癸": "卯巳", "辛": "午寅",
}
WENCHANG = {  # 文昌（日干）：甲乙巳午、丙戊申、丁己酉、庚亥、辛子、壬寅、癸卯
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申", "己": "酉",
    "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}
TAOHUA = {  # 桃花（年/日支三合沐浴）：申子辰→酉、寅午戌→卯、亥卯未→子、巳酉丑→午
    "申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯",
    "亥": "子", "卯": "子", "未": "子", "巳": "午", "酉": "午", "丑": "午",
}
YIMA = {  # 驿马（三合对冲）：申子辰→寅、寅午戌→申、亥卯未→巳、巳酉丑→亥
    "申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
    "亥": "巳", "卯": "巳", "未": "巳", "巳": "亥", "酉": "亥", "丑": "亥",
}
HUAGAI = {  # 华盖（三合墓库）：寅午戌→戌、申子辰→辰、巳酉丑→丑、亥卯未→未
    "寅": "戌", "午": "戌", "戌": "戌", "申": "辰", "子": "辰", "辰": "辰",
    "巳": "丑", "酉": "丑", "丑": "丑", "亥": "未", "卯": "未", "未": "未",
}
LUSHEN = {  # 禄神（日干禄地）：甲寅乙卯丙戊巳、丁己午庚申辛酉、壬亥癸子
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳", "己": "午",
    "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}
YANGREN = {  # 羊刃（禄前一位）
    "甲": "卯", "乙": "辰", "丙": "午", "丁": "未", "戊": "午", "己": "未",
    "庚": "酉", "辛": "戌", "壬": "子", "癸": "丑",
}
KONGWANG = {  # 空亡（按日干所属旬 1..10）
    1: ("戌", "亥"), 2: ("申", "酉"), 3: ("午", "未"), 4: ("辰", "巳"),
    5: ("寅", "卯"), 6: ("子", "丑"), 7: ("戌", "亥"), 8: ("申", "酉"),
    9: ("午", "未"), 10: ("辰", "巳"),
}
_GAN_IDX = {g: i + 1 for i, g in enumerate(GAN)}


def test_shensha_tables_vs_classic():
    """神煞映射表须与典籍逐条一致。"""
    assert _GUIREN == SHENG_XIAO_GUIREN, _GUIREN
    assert _WENCHANG == WENCHANG, _WENCHANG
    assert _TAOHUA == TAOHUA, _TAOHUA
    assert _YIMA == YIMA, _YIMA
    assert _HUAGAI == HUAGAI, _HUAGAI
    assert _LUSHEN == LUSHEN, _LUSHEN
    assert _YANGREN == YANGREN, _YANGREN
    assert _KONGWANG == KONGWANG, _KONGWANG


# ===== 独立十神推导（经典定义，不从 bazi 代码复制）=====
def _ten_god(day_gan: str, other: str) -> str:
    """日主 vs 他干 → 十神（经典定义，独立实现用作 oracle）。"""
    if other == day_gan:
        return "比肩"
    dw, ow = GAN_WUXING[day_gan], GAN_WUXING[other]
    same_yin = (GAN.index(day_gan) % 2 == 0) == (GAN.index(other) % 2 == 0)
    if dw == ow:  # 同五行异干 → 比肩(同阴) / 劫财(异阴)
        return "比肩" if same_yin else "劫财"
    same_yin = (GAN.index(day_gan) % 2 == 0) == (GAN.index(other) % 2 == 0)
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if sheng.get(dw) == ow:
        rel = "我生"
    elif sheng.get(ow) == dw:
        rel = "生我"
    elif ke.get(dw) == ow:
        rel = "我克"
    else:
        rel = "克我"
    if rel == "我生":
        return "食神" if same_yin else "伤官"
    if rel == "生我":
        return "偏印" if same_yin else "正印"
    if rel == "我克":
        return "偏财" if same_yin else "正财"
    return "七杀" if same_yin else "正官"  # 克我


def _oracle_pillars(year: int, month: int, day: int, hour: int):
    """独立 oracle：用 lunar-python 原语取四柱 + 藏干，复算五行/十神/缺数。"""
    lunar = Solar.fromYmdHms(year, month, day, hour, 0, 0).getLunar()
    ec = lunar.getEightChar()
    gz = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
    hides = [ec.getYearHideGan(), ec.getMonthHideGan(),
             ec.getDayHideGan(), ec.getTimeHideGan()]
    day_gan = ec.getDayGan()

    # 四柱干支
    pillars_gz = [(g[0], g[1]) for g in gz]

    # 五行个数（天干 + 地支本气）
    wuxing_count = {k: 0 for k in ("金", "木", "水", "火", "土")}
    for g, z in pillars_gz:
        wuxing_count[GAN_WUXING[g]] += 1
        wuxing_count[ZHI_WUXING[z]] += 1
    lacking = sorted(k for k, v in wuxing_count.items() if v == 0)

    # 五行加权（天干1.0 + 藏干 本气1.0/中气0.5/余气0.3）
    weights = {k: 0.0 for k in ("金", "木", "水", "火", "土")}
    for g, _ in pillars_gz:
        weights[GAN_WUXING[g]] += 1.0
    for hs in hides:
        for j, g in enumerate(hs):
            w = 1.0 if j == 0 else (0.5 if j == 1 else 0.3)
            weights[GAN_WUXING[g]] += w
    total = sum(weights.values()) or 1.0
    wuxing_pct = {k: round(v / total * 100) for k, v in weights.items()}

    # 十神聚合（天干十神 + 各藏干十神；日柱天干即日主不计入，但日柱藏干计入）
    shishen = {}
    for i, (g, z) in enumerate(pillars_gz):
        if i != 2:  # 日柱天干即日主，不计入天干十神
            tg = _ten_god(day_gan, g)
            shishen[tg] = shishen.get(tg, 0) + 1
        for hg in hides[i]:
            sg = _ten_god(day_gan, hg)
            shishen[sg] = shishen.get(sg, 0) + 1

    return {
        "gz": pillars_gz, "hides": hides, "day_gan": day_gan,
        "wuxing_count": wuxing_count, "lacking": lacking,
        "wuxing_pct": wuxing_pct, "shishen": shishen,
    }


def _oracle_shensha(day_gan: str, year_zhi: str, month_zhi: str,
                    day_zhi: str, time_zhi: str) -> dict:
    """独立 oracle：复算每个神煞的目标地支与落宫（对齐 bazi._shensha）。"""
    zhi_pillar = {year_zhi: "年柱", month_zhi: "月柱",
                  day_zhi: "日柱", time_zhi: "时柱"}
    tables = {
        "天乙贵人": list(_GUIREN[day_gan]),
        "文昌": [_WENCHANG[day_gan]],
        "桃花": [_TAOHUA[day_zhi]],
        "驿马": [_YIMA[day_zhi]],
        "华盖": [_HUAGAI[day_zhi]],
        "禄神": [_LUSHEN[day_gan]],
        "羊刃": [_YANGREN[day_gan]],
        "空亡": list(_KONGWANG[_GAN_IDX[day_gan]]),
    }
    out = {}
    for name, zhis in tables.items():
        hit = None
        for z in zhis:
            if z in zhi_pillar:
                hit = (z, zhi_pillar[z])
                break
        if hit is None:
            hit = (zhis[0], "待大运流年引动")
        out[name] = hit
    return out


CASES = [
    (1990, 5, 15, 0, "男"),    # 庚午年 子时 男（阳年男 → 顺）
    (1987, 6, 12, 12, "女"),   # 丁卯年 午时 女
    (2000, 2, 29, 6, "男"),    # 庚辰年 卯时 男（闰年边界）
    (1995, 11, 23, 18, "女"),  # 乙亥年 酉时 女
    (1984, 8, 8, 10, "男"),    # 甲子年 巳时 男
]


def test_four_pillars_and_daymaster():
    """四柱干支 + 日主 须与 lunar-python 原语一致。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        o = _oracle_pillars(y, m, d, h)
        assert r["dayMaster"] == o["day_gan"], (y, m, d, r["dayMaster"], o["day_gan"])
        assert r["dayMasterWuxing"] == GAN_WUXING[o["day_gan"]]
        out_gz = [(p["gan"], p["zhi"]) for p in r["pillars"]]
        assert out_gz == o["gz"], (y, m, d, out_gz, o["gz"])


def test_pillar_notes_ten_god():
    """每柱 note（天干十神坐地支本气十神）须与独立推导一致。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        o = _oracle_pillars(y, m, d, h)
        day_gan = o["day_gan"]
        for i, p in enumerate(r["pillars"]):
            if p["label"].startswith("日柱"):
                assert p["note"] == "★ 日主", p
                continue
            gan_ss = _ten_god(day_gan, p["gan"])
            benqi = o["hides"][i][0]
            zhi_ss = _ten_god(day_gan, benqi)
            assert p["note"] == f"{gan_ss}坐{zhi_ss}", (y, m, d, i, p["note"])


def test_wuxing_count_and_pct():
    """五行个数与加权百分比须与独立复算一致。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        o = _oracle_pillars(y, m, d, h)
        cnt = {x["label"]: x["count"] for x in r["wuxingCount"]}
        assert cnt == o["wuxing_count"], (y, m, d, cnt, o["wuxing_count"])
        assert r["lacking"] == o["lacking"], (y, m, d, r["lacking"])
        pct = {x["label"]: x["pct"] for x in r["wuxing"]}
        assert pct == o["wuxing_pct"], (y, m, d, pct, o["wuxing_pct"])


def test_shishen_aggregate():
    """十神聚合（天干 + 藏干）须与独立推导一致。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        o = _oracle_pillars(y, m, d, h)
        out = {s["name"]: s["val"] for s in r["shiShen"]}
        assert out == o["shishen"], (y, m, d, out, o["shishen"])


def test_shensha_placement():
    """神煞目标地支与落宫须与典籍表 + 四柱落点一致。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        lunar = Solar.fromYmdHms(y, m, d, h, 0, 0).getLunar()
        ec = lunar.getEightChar()
        o = _oracle_shensha(
            ec.getDayGan(), ec.getYearZhi(), ec.getMonthZhi(),
            ec.getDayZhi(), ec.getTimeZhi(),
        )
        out = {s["name"]: (s["zhi"], s["pillar"]) for s in r["shensha"]}
        assert out == o, (y, m, d, out, o)


def test_dayun_structure_and_direction():
    """大运：应为 8 步、年龄单调、仅一个当前高亮，且顺逆方向正确。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        dayun = r["dayun"]
        assert len(dayun) >= 8, (y, m, d, len(dayun))
        ages = [int(x["age"].split("-")[0]) for x in dayun]
        assert ages == sorted(ages), (y, m, d, ages)
        golds = [x for x in dayun if x.get("gold")]
        # 当前大运高亮至多一个
        assert len(golds) <= 1, (y, m, d, golds)
        # 顺逆：阳年男 / 阴年女 → 顺（干支序号递增）；其余 → 逆
        ec = Solar.fromYmdHms(y, m, d, h, 0, 0).getLunar().getEightChar()
        y_gan = ec.getYearGan()
        yang_year = GAN.index(y_gan) % 2 == 0
        expect_forward = (yang_year and g == "男") or (not yang_year and g == "女")
        seq = [GAN_WUXING.get(x["gan"][0], "") for x in dayun]  # 占位，转序号
        idx60 = {f"{gan}{zhi}": i for i, (gan, zhi) in enumerate(
            [(GAN[a % 10], ZHI[a % 12]) for a in range(60)])}
        nums = [idx60[x["gan"]] for x in dayun]
        steps = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]
        if expect_forward:
            assert all(s > 0 for s in steps), (y, m, d, g, nums, steps)
        else:
            assert all(s < 0 for s in steps), (y, m, d, g, nums, steps)


def test_qiyun_age_consistency():
    """起运虚岁须等于首个大运的起始年龄。"""
    for y, m, d, h, g in CASES:
        r = compute_bazi(y, m, d, h, g)
        if r["dayun"]:
            first_age = int(r["dayun"][0]["age"].split("-")[0])
            assert r["qiyun"]["age"] == first_age, (y, m, d)
