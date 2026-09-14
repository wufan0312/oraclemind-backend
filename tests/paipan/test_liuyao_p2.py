# -*- coding: utf-8 -*-
"""六爻 P2（高阶辩证）单测：游魂/归魂、反呤/伏呤、卦身、三合六冲。

运行：cd oraclemind-backend && .venv/Scripts/python.exe -m pytest tests/paipan/test_liuyao_p2.py -q
"""
import pytest

from app.services.paipan.yijing_data import (
    guahun_of,
    fan_fu_of,
    guashen_of,
    sanhe_of,
    liuhe_pairs,
    liuchong_pairs,
    hexagram_by_upper_lower,
)
from app.services.paipan.liuyao import compute_liuyao


# ============ 游魂 / 归魂 ============
def test_guahun_youhun_guinhun():
    # 八宫序号：6=游魂，7=归魂
    assert guahun_of(hexagram_by_upper_lower("乾", "坎")) == "游魂"   # 天水讼
    assert guahun_of(hexagram_by_upper_lower("乾", "离")) == "归魂"   # 天火同人
    assert guahun_of(hexagram_by_upper_lower("乾", "乾")) == ""       # 本宫
    assert guahun_of(hexagram_by_upper_lower("离", "巽")) == ""       # 二世卦


# ============ 反呤 / 伏呤 ============
def test_fan_fu():
    ben = hexagram_by_upper_lower("乾", "乾")        # 乾为天
    bian_fan = hexagram_by_upper_lower("坤", "坤")   # 坤为地（内外均冲）
    bian_fu = hexagram_by_upper_lower("乾", "乾")    # 同卦（仅爻动）

    # 反呤：变卦内外卦均与本卦相冲，需有动爻
    assert fan_fu_of(ben, bian_fan, True) == ("反呤", "")
    # 伏呤：变卦与本卦同体，需有动爻方论
    assert fan_fu_of(ben, bian_fu, True) == ("", "伏呤")
    # 无动爻则不论伏呤
    assert fan_fu_of(ben, bian_fu, False) == ("", "")
    # 无变卦则皆空
    assert fan_fu_of(ben, None, True) == ("", "")


# ============ 卦身 ============
def test_guashen_position_range():
    # 天风姤（乾+巽）：项目数据中世在四爻(4, 阴位) → 从午起数
    ben = hexagram_by_upper_lower("乾", "巽")
    gs = guashen_of(ben, "申", "酉")
    assert isinstance(gs["yuePos"], int) and 1 <= gs["yuePos"] <= 6
    assert isinstance(gs["riPos"], int) and 1 <= gs["riPos"] <= 6
    assert gs["yangShi"] is False

    # 风地观（巽+坤）：项目数据中世在初爻(1, 阳位) → 从子起数
    ben_yang = hexagram_by_upper_lower("巽", "坤")
    gs2 = guashen_of(ben_yang, "子", "子")
    assert gs2["yangShi"] is True
    assert gs2["yuePos"] == 1  # 月建=子，与 start(子) 同，落在初爻
    # 月建=丑 → 二爻
    gs3 = guashen_of(ben_yang, "丑", "丑")
    assert gs3["yuePos"] == 2


# ============ 三合局 ============
def test_sanhe():
    assert sanhe_of(["申", "子", "辰", "丑"]) == ["水"]
    assert set(sanhe_of(["亥", "卯", "未", "午"])) == {"木"}
    # 不全不成局
    assert sanhe_of(["申", "子"]) == []
    # 多局
    assert set(sanhe_of(["申", "子", "辰", "亥", "卯", "未"])) == {"水", "木"}


# ============ 六合 / 六冲 ============
def test_liuhe_liuchong():
    assert [''.join(p) for p in liuhe_pairs(["子", "丑", "寅"])] == ["子丑"]
    assert [''.join(p) for p in liuhe_pairs(["子", "卯"])] == []
    assert [''.join(p) for p in liuchong_pairs(["子", "午", "卯"])] == ["子午"]
    assert [''.join(p) for p in liuchong_pairs(["子", "丑"])] == []


# ============ 集成：compute_liuyao 产出 special 结构 ============
def test_compute_liuyao_special_structure():
    r = compute_liuyao(2026, 8, 27, 15, "男", "申时", "事业")
    sp = r["special"]
    # 关键字段齐全
    for k in ("guahun", "bianGuahun", "fan", "fu", "guashen",
              "sanhe", "sanheCheng", "liuhe", "liuchong", "involved"):
        assert k in sp, f"special 缺字段 {k}"
    # 卦身位置合法
    assert 1 <= sp["guashen"]["yuePos"] <= 6
    assert 1 <= sp["guashen"]["riPos"] <= 6
    # sanhe 与 sanheCheng 键一致
    assert set(sp["sanhe"]) == set(sp["sanheCheng"].keys())
    # 合冲段落已接入解读
    titles = [a["title"] for a in r["analysis"]]
    assert "卦体特殊" in titles
    assert "全局合冲" in titles
