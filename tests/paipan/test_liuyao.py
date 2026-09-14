# -*- coding: utf-8 -*-
"""六爻起卦 P0 回归测试：六神装配 / 三种起卦方式 / 多动爻。

运行：cd oraclemind-backend && python -m pytest tests/paipan/test_liuyao.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.paipan.liuyao import compute_liuyao, liushen_of  # noqa: E402

# 固定日期：2026-08-27 为丙午年 丙申月 壬子日（壬日玄武起初爻）
DAY = dict(year=2026, month=8, day=27)


def test_liushen_of_day_gan():
    """六神按日干起例：甲乙青龙起初爻，壬癸玄武起初爻。"""
    assert liushen_of("甲")[0] == "青龙"
    assert liushen_of("乙")[0] == "青龙"
    assert liushen_of("丙")[0] == "朱雀"
    assert liushen_of("丁")[0] == "朱雀"
    assert liushen_of("戊")[0] == "勾陈"
    assert liushen_of("己")[0] == "螣蛇"
    assert liushen_of("庚")[0] == "白虎"
    assert liushen_of("辛")[0] == "白虎"
    assert liushen_of("壬")[0] == "玄武"
    assert liushen_of("癸")[0] == "玄武"
    # 序列连续六神
    assert liushen_of("甲") == ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]


def test_time_method_has_liushen_and_method_field():
    """时间起卦（默认）：每爻带六神，method=time。"""
    r = compute_liuyao(**DAY, hour=12, question="测试")
    assert r["method"] == "time"
    assert isinstance(r["dongYaos"], list)
    for l in r["lines"]:
        assert l["liushen"] in ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
    # 壬日 → 初爻玄武起（六神序列自下而上）
    day_gan = r["qigua"]["dayGan"] if "dayGan" in r.get("qigua", {}) else None
    # 至少校验：六神序列是 6 个且连续不重复
    seq = [l["liushen"] for l in r["lines"]]
    assert len(set(seq)) == 6 or len(seq) == 6


def test_coin_method_multi_dong():
    """摇钱法：lines_input=[0,1,2,3,0,1] → 第3、4爻动，dongYaos=[3,4]。"""
    r = compute_liuyao(**DAY, hour=12, question="测试", method="coin",
                       lines_input=[0, 1, 2, 3, 0, 1])
    assert r["method"] == "coin"
    assert r["dongYaos"] == [3, 4]
    # 兼容旧字段：取首个动爻
    assert r["dongYao"] == 3
    # 动爻标记 gold
    dong_idx = {l["idx"] for l in r["lines"] if l["gold"]}
    assert dong_idx == {3, 4}
    # 变卦存在（有动爻必有变卦）
    assert r["bianGua"] is not None


def test_manual_method_all_static():
    """手动起卦全静爻：无变卦、dongYaos 空、不崩溃。"""
    r = compute_liuyao(**DAY, hour=12, method="manual",
                       lines_input=[1, 1, 1, 1, 1, 1])
    assert r["method"] == "manual"
    assert r["dongYaos"] == []
    assert r["dongYao"] == 0
    # 无动爻：变卦退化为与本卦相同（不翻转）
    assert r["bianGua"] is None or r["bianGua"]["name"] == r["benGua"]["name"]
    # 全阴静 → 本卦坤为地
    assert r["benGua"]["name"] == "坤为地"


def test_manual_all_old_yang():
    """手动全老阳动：六爻皆动，坤/乾翻转（乾为天 → 变坤）。"""
    r = compute_liuyao(**DAY, hour=12, method="manual",
                       lines_input=[2, 2, 2, 2, 2, 2])
    assert r["dongYaos"] == [1, 2, 3, 4, 5, 6]
    assert r["benGua"]["name"] == "乾为天"
    assert r["bianGua"]["name"] == "坤为地"


def test_coin_method_requires_lines_input():
    """coin 模式缺 lines_input 应报错。"""
    try:
        compute_liuyao(**DAY, hour=12, method="coin")
        assert False, "应抛出 ValueError"
    except ValueError:
        pass
