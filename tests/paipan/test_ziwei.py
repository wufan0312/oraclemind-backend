# -*- coding: utf-8 -*-
"""紫微斗数排盘回归测试：锁定安星口径与新增模块（P0~P3）。

运行：cd oraclemind-backend && python -m pytest tests/paipan/test_ziwei.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.paipan.ziwei import (  # noqa: E402
    compute_ziwei, HUO_LING, GU_CHEN, GUA_SU, _xunkong, _xiaoxian_zhi,
    _gz_index, _changsheng_for, _palace_sihua, ZHI_ORDER, GAN_ORDER,
    NAYIN_NAME, _nayin, JU_BY_NAYIN,
)


def test_gz_index_known():
    """六十甲子序号 / 纳音 关键校验。"""
    # 庚午 -> 干支序 6 -> 路旁土(土5)
    gi, zi = GAN_ORDER.index("庚"), ZHI_ORDER.index("午")
    idx = _gz_index("庚", "午")
    assert idx == 6, idx
    assert _nayin(idx) == "路旁土"
    assert JU_BY_NAYIN[_nayin(idx)[-1]] == 5
    # 甲子 -> 0 -> 海中金(金4)
    assert _gz_index("甲", "子") == 0
    assert _nayin(0) == "海中金"
    assert JU_BY_NAYIN["金"] == 4


def test_huo_ling_mars_bugfix():
    """P3：寅午戌年生人火星应入丑(1)，其余三合不变。"""
    assert HUO_LING["寅"][0] == 1  # 丑
    assert HUO_LING["申"][0] == 2  # 寅
    assert HUO_LING["巳"][0] == 3  # 卯
    assert HUO_LING["亥"][0] == 9  # 酉
    # 铃星四组合不受影响
    assert HUO_LING["寅"][1] == 3
    assert HUO_LING["亥"][1] == 10


def test_guchen_guasu():
    """孤辰寡宿：午年生人 孤辰巳(5) / 寡宿辰(4)。"""
    assert GU_CHEN["午"] == 5
    assert GUA_SU["午"] == 4


def test_xunkong():
    """旬空：庚午(甲子旬) 戌亥空(10,11)。"""
    gi, zi = GAN_ORDER.index("庚"), ZHI_ORDER.index("午")
    idx = _gz_index("庚", "午")
    assert _xunkong(idx) == [10, 11]


def test_xiaoxian():
    """小限：午年生人 虚岁37 -> 午(6)（生年支起1岁顺数）。"""
    assert _xiaoxian_zhi(ZHI_ORDER.index("午"), 37) == 6
    assert _xiaoxian_zhi(ZHI_ORDER.index("寅"), 1) == 2  # 寅年生人1岁在寅


def test_palace_gan_woohu():
    """宫干：庚年正月(寅)宫干=戊（乙庚之岁戊为头）。"""
    yin = (GAN_ORDER.index("庚") * 2 + 2) % 10
    assert GAN_ORDER[yin] == "戊"


def test_changsheng_sequence():
    """长生十二神返回 12 宫且为合法 stage 名。"""
    cs = _changsheng_for(5, "男", "庚")
    assert len(cs) == 12
    assert set(cs.values()) <= {
        "长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"
    }


def test_full_chart_1990():
    """整盘跑通 + 新增字段存在且自洽（1990 庚午 男 未时）。"""
    r = compute_ziwei(1990, 6, 15, 14, "男", "未时")
    assert len(r["palaces"]) == 12
    # 五行局自洽：丁亥 屋上土（土5）
    assert r["wuxingJu"].startswith("屋上土")
    assert "5局" in r["wuxingJu"]
    # 新增字段
    assert isinstance(r["patterns"], list) and r["patterns"]
    assert r["xiaoXian"]["palace"] in [p["name"] for p in r["palaces"]]
    assert r["liuNianSihuaRange"]
    assert r["liuYueSihuaByYear"]
    assert len(r["palaceSihua"]) > 0
    # 各宫含新键
    for p in r["palaces"]:
        assert "misc" in p and "changsheng" in p and "borrow" in p
    # 空宫应有借星（对宫主星）
    empty = [p for p in r["palaces"] if p["star"] in ("—", "")]
    for p in empty:
        assert p["borrow"]  # 对宫至少借到主星


def test_palace_sihua_self():
    """宫干四化：含自化（同宫）标记。"""
    ps = _palace_sihua(
        ["甲"] * 12,
        {"廉贞": 0, "破军": 1, "武曲": 2, "太阳": 3},
    )
    # 甲年：禄廉贞 权破军 科武曲 忌太阳
    stars = {x["star"] for x in ps}
    assert {"廉贞", "破军", "武曲", "太阳"} <= stars
    assert all(x["hua"] in ("禄", "权", "科", "忌") for x in ps)
