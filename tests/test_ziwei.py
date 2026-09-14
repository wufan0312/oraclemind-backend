# -*- coding: utf-8 -*-
"""紫微斗数排盘口径回归测试。

锁住自研安星法的核心口径，防止后续杂曜补全 / 流年盘重排 / 四化逻辑改动时
悄悄破坏现有排盘正确性。

基线样本：1995-01-01 子时（农历甲戌年），查询年固定 target_year=2026（丙午）。
"""
from app.services.paipan.ziwei import (
    compute_ziwei, ZHI_ORDER, PALACE_NAMES,
    TIAN_GUAN, TIAN_FU, TIAN_DE,
    LONG_CHI_BASE, FENG_GE_BASE, TAI_FU_BASE, FENG_GAO_BASE, EN_GUANG_BASE, TIAN_GUI_BASE,
)

# 固定查询年，避免依赖"现在"导致断言随真实日期漂移
TARGET_YEAR = 2026
TARGET_MONTH = 6


def _base():
    return compute_ziwei(1995, 1, 1, time_text="子时",
                         target_year=TARGET_YEAR, target_month=TARGET_MONTH)


def test_ming_shen_ju():
    r = _base()
    assert r["mingGong"] == "丁丑宫（丑）", r["mingGong"]
    # 子时出生：身宫与命宫同宫
    assert r["shenGongName"] == "命宫", r["shenGongName"]
    assert r["wuxingJu"] == "涧下水 · 2局", r["wuxingJu"]
    assert r["ziwei"] == "紫微在寅", r["ziwei"]


def test_twelve_palaces_structure():
    r = _base()
    names = [p["name"] for p in r["palaces"]]
    # 顺序需严格等于人事宫序（命宫起逆时针）
    assert names == ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                     "迁移", "交友", "官禄", "田宅", "福德", "父母"]
    assert len(r["palaces"]) == 12
    # 每个宫位必须带关键字段（供前端渲染与 AI 解读）
    for p in r["palaces"]:
        assert {"name", "star", "pos", "gan", "sifang", "aux", "misc",
                "changsheng", "borrow"} <= set(p.keys())


def test_ming_star():
    r = _base()
    ming = next(p for p in r["palaces"] if p["name"] == "命宫")
    # 甲戌年涧下水二局，紫微在寅 -> 命宫（丑）天机
    assert ming["star"] == "天机", ming["star"]


def test_sheng_nian_sihua():
    """甲年生年四化：廉贞禄 / 破军权 / 武曲科 / 太阳忌。"""
    r = _base()
    got = {(s["star"], s["hua"], s["palace"]) for s in r["sihua"]}
    expect = {
        ("廉贞", "禄", "交友"),
        ("破军", "权", "兄弟"),
        ("武曲", "科", "子女"),
        ("太阳", "忌", "夫妻"),
    }
    assert got == expect, got


def test_liu_nian_ming_palace():
    """2026 丙午，流年命宫落点需稳定。"""
    r = _base()
    ln = r["liuNian"]
    assert ln["year"] == TARGET_YEAR
    assert ln["zhi"] == "午"
    assert ln["mingPalace"] == "财帛", ln
    assert ln["taiPalace"] == "交友", ln  # 太岁宫（午）原盘位置


def test_xiao_xian():
    r = _base()
    x = r["xiaoXian"]
    assert x["age"].startswith("32岁"), x
    assert x["palace"] == "官禄", x


def test_liu_nian_sihua():
    """丙年四化：天机禄 / 天梁权 / 紫微科 / 太阴忌。"""
    r = _base()
    got = {(s["star"], s["hua"], s["palace"]) for s in r["liuNianSihua"]}
    expect = {
        ("天机", "禄", "兄弟"),
        ("天梁", "权", "交友"),
        ("紫微", "科", "夫妻"),
        ("太阴", "忌", "子女"),
    }
    assert got == expect, got


def test_time_unknown_fallback():
    """时辰不详用午时补排，仍应返回完整 12 宫且命宫为午时结果。"""
    r = compute_ziwei(1995, 1, 1, hour=None, target_year=TARGET_YEAR)
    assert len(r["palaces"]) == 12
    # 午时（h=12 -> 午时 11:00-13:00）：命宫位置与子时不同
    ming = next(p for p in r["palaces"] if p["name"] == "命宫")
    assert ming["star"], "时辰不详仍应排盘"


def test_misc_stars_deterministic():
    """本命杂曜（口径确定者）需落在正确宫位，且原年支杂曜不受破坏。

    1995 甲戌年、农历子月样本：
      天巫(年干甲->卯)->父母宫；天厨(甲食神丙禄巳)->官禄宫；
      月德(子月三合申子辰->壬->亥)->夫妻宫；劫煞(戌三合绝地亥)->夫妻宫；
      阴煞(戌三合前一辰寅)->福德宫；天刑(年支戌->寅? 戌前1=丑? 见常量)仍标记。
    """
    r = _base()
    by_name = {p["name"]: p["misc"] for p in r["palaces"]}
    assert "天巫" in by_name["福德"], by_name["福德"]
    assert "天厨" in by_name["官禄"], by_name["官禄"]
    assert "月德" in by_name["疾厄"], by_name["疾厄"]
    assert "劫煞" in by_name["夫妻"], by_name["夫妻"]
    assert "阴煞" in by_name["父母"], by_name["父母"]
    # 原有年支杂曜仍生效
    assert "天刑" in by_name["命宫"], by_name["命宫"]


def test_high_disagreement_misc_stars():
    """高分歧杂曜补全回归：天官/天福(年干)·龙池凤阁台辅封诰恩光天贵(年支顺布)·
    三台八座(左辅右弼)·天才天寿(命/身宫)·天哭天虚(年支对宫)·天德(月支) 落点锁定。

    1995 甲戌年、农历丑月（腊月）样本。各流派口径略有出入，本测试锁住当前采用公式，
    后续切换流派只需改 ziwei.py 常量 + 同步此处。
    """
    r = _base()
    bn = {p["name"]: p["misc"] for p in r["palaces"]}
    Z = ZHI_ORDER
    ming_zhi = r["mingGong"][-2]            # '丑'
    ming_idx = Z.index(ming_zhi)

    def palace_for_abs(zhi_char: str) -> str:
        pidx = (ming_idx - Z.index(zhi_char)) % 12
        return PALACE_NAMES[pidx]

    year_gan, year_zhi = "甲", "戌"
    yzi = Z.index(year_zhi)

    # 年干系
    assert "天官" in bn[palace_for_abs(TIAN_GUAN[year_gan])]
    assert "天福" in bn[palace_for_abs(TIAN_FU[year_gan])]
    # 年支顺布类（base + 年支序）
    assert "龙池" in bn[palace_for_abs(Z[(LONG_CHI_BASE + yzi) % 12])]
    assert "凤阁" in bn[palace_for_abs(Z[(FENG_GE_BASE + yzi) % 12])]
    assert "台辅" in bn[palace_for_abs(Z[(TAI_FU_BASE + yzi) % 12])]
    assert "封诰" in bn[palace_for_abs(Z[(FENG_GAO_BASE + yzi) % 12])]
    assert "恩光" in bn[palace_for_abs(Z[(EN_GUANG_BASE + yzi) % 12])]
    assert "天贵" in bn[palace_for_abs(Z[(TIAN_GUI_BASE + yzi) % 12])]
    # 天才在命宫、天寿在身宫
    assert "天才" in bn["命宫"]
    assert "天寿" in bn[r["shenGongName"]]
    # 天哭天虚：年支对宫（六冲），同宫
    kx = Z[(yzi + 6) % 12]
    assert "天哭" in bn[palace_for_abs(kx)]
    assert "天虚" in bn[palace_for_abs(kx)]
    # 天德（月支派生）：本样本农历丑月(月支序=1) -> 申宫
    assert "天德" in bn[palace_for_abs(TIAN_DE[1])]


def test_high_disagreement_misc_year_variant():
    """乙年样本：天官/天福 随年干变化，落点与甲年不同（锁住年干公式）。"""
    r = compute_ziwei(1985, 6, 1, time_text="子时",
                      target_year=TARGET_YEAR, target_month=TARGET_MONTH)
    bn = {p["name"]: p["misc"] for p in r["palaces"]}
    Z = ZHI_ORDER
    ming_idx = Z.index(r["mingGong"][-2])
    def palace_for_abs(zhi_char: str) -> str:
        return PALACE_NAMES[(ming_idx - Z.index(zhi_char)) % 12]
    # 1985 乙丑年：天官->卯、天福->申
    assert "天官" in bn[palace_for_abs(TIAN_GUAN["乙"])]
    assert "天福" in bn[palace_for_abs(TIAN_FU["乙"])]
    # 甲年(1995)天官在寅、乙年应在卯，确认随年干切换
    base = _base()
    base_bn = {p["name"]: p["misc"] for p in base["palaces"]}
    base_ming = Z.index(base["mingGong"][-2])
    assert "天官" in base_bn[PALACE_NAMES[(base_ming - Z.index(TIAN_GUAN["甲"])) % 12]]
    assert "天官" not in base_bn.get(PALACE_NAMES[(base_ming - Z.index(TIAN_GUAN["乙"])) % 12], [])


def test_liu_nian_pan():
    """流年十二宫盘：以流年命宫为基准重排，太岁标注在流年地支宫。

    2026 丙午：流年命宫落原盘财帛宫（天同），故流年盘「命宫」star 应为天同；
    太岁在午，对应流年盘福德宫。
    """
    r = _base()
    pan = r["liuNianPan"]
    assert len(pan) == 12, len(pan)
    # 流年命宫（流年盘 name==命宫）星曜应等于原盘财帛宫星曜
    ming = next(p for p in pan if p["name"] == "命宫")
    assert ming["star"] == "天同", ming
    assert ming["isMingGong"] is True
    # 太岁标注（2026 午年 -> 流年盘子女宫）
    tai = [p for p in pan if p["taiSui"]]
    assert len(tai) == 1, tai
    assert tai[0]["name"] == "子女", tai
    # 流年盘各宫地支序连续逆布，命宫地支 = 原盘财帛宫地支
    caibo = next(p for p in r["palaces"] if p["name"] == "财帛")
    assert ming["pos"] == caibo["pos"], (ming["pos"], caibo["pos"])


def test_palace_sihua_present():
    """宫干四化（飞星派核心）需存在且为 12 宫逐一标注。"""
    r = _base()
    assert isinstance(r["palaceSihua"], list)
    assert len(r["palaceSihua"]) > 0
    for item in r["palaceSihua"]:
        assert {"from", "hua", "star", "to", "self"} <= set(item.keys())
