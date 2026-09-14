# -*- coding: utf-8 -*-
"""六爻起卦 P1 旺衰/动变深度测试。

运行：cd oraclemind-backend && python -m pytest tests/paipan/test_liuyao_p1.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.paipan.yijing_data import (  # noqa: E402
    changsheng_table,
    changsheng_of,
    is_an_dong,
    is_hua_mu,
    is_ru_mu,
    is_yue_po,
    jin_tui_shen,
    mu_zhi_of,
)
from app.services.paipan.liuyao import compute_liuyao  # noqa: E402

# 2026-08-27 为丙午年 丙申月 壬子日（壬→水，日干五行起长生在申）
DAY = dict(year=2026, month=8, day=27)


def test_changsheng_base():
    """十二长生起例：木长生亥、火长生寅、金长生巳、水长生申、土随水长生申。"""
    cs_mu = changsheng_table("木")
    assert cs_mu["亥"] == "长生"
    assert cs_mu["子"] == "沐浴"
    assert cs_mu["卯"] == "帝旺"
    cs_huo = changsheng_table("火")
    assert cs_huo["寅"] == "长生"
    assert cs_huo["午"] == "帝旺"
    cs_jin = changsheng_table("金")
    assert cs_jin["巳"] == "长生"
    assert cs_jin["酉"] == "帝旺"
    cs_shui = changsheng_table("水")
    assert cs_shui["申"] == "长生"
    assert cs_shui["子"] == "帝旺"
    assert changsheng_table("土")["申"] == "长生"  # 土随水


def test_jin_tui_shen():
    """进退神：寅→卯化进、卯→寅化退、跨五行无进退。"""
    assert jin_tui_shen("寅", "卯") == "化进"
    assert jin_tui_shen("卯", "寅") == "化退"
    assert jin_tui_shen("申", "酉") == "化进"
    assert jin_tui_shen("酉", "申") == "化退"
    assert jin_tui_shen("亥", "子") == "化进"
    assert jin_tui_shen("寅", "辰") == ""  # 跨五行无进退


def test_yue_po():
    """月破：子午冲、丑未冲；非冲则否。"""
    assert is_yue_po("子", "午") is True
    assert is_yue_po("午", "子") is True
    assert is_yue_po("丑", "未") is True
    assert is_yue_po("子", "丑") is False


def test_an_dong():
    """暗动：静爻被日冲且得月建生扶（旺/相）方为暗动。"""
    # 午日冲子，子水爻在申月（金生水→相）→ 暗动
    assert is_an_dong("子", "水", "申", "午") is True
    # 子日冲午，午火爻在申月（火囚）→ 不暗动
    assert is_an_dong("午", "火", "申", "子") is False


def test_hua_mu_and_ru_mu():
    """墓库与化墓：木墓在未；动爻化出未（木爻）为化墓。"""
    assert mu_zhi_of("木") == "未"
    assert mu_zhi_of("火") == "戌"
    assert mu_zhi_of("水") == "辰"
    assert is_hua_mu("未", "木") is True
    assert is_hua_mu("申", "木") is False


def test_integration_lines_have_p1_fields():
    """集成：时间起卦每爻带 P1 字段，用神含世爻旺衰，分析含新段落。"""
    r = compute_liuyao(**DAY, hour=12, question="求财")
    for l in r["lines"]:
        for f in ("changsheng", "yuePo", "anDong", "ruMu", "jinTui", "houtou", "huaMu"):
            assert f in l, f"爻缺失字段 {f}"
        # changsheng 必须是十二长生之一
        assert l["changsheng"] in (
            "长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"
        )
    assert "shiStrength" in r["yongshen"]
    assert "shiStrengthNote" in r["yongshen"]
    titles = [p["title"] for p in r["analysis"]]
    assert "动变深度" in titles
    assert "特殊爻象" in titles
    assert "用神旺衰" in titles


def test_integration_coin_multi_dong_has_depth():
    """集成：摇钱法多动爻，动爻行含进退/回头生克/化墓字段。"""
    r = compute_liuyao(**DAY, hour=12, method="coin",
                       lines_input=[0, 1, 2, 3, 0, 1], question="事业")
    dong_lines = [l for l in r["lines"] if l["idx"] in (3, 4)]
    assert dong_lines, "应有两个动爻"
    for l in dong_lines:
        for f in ("jinTui", "houtou", "huaMu"):
            assert f in l
