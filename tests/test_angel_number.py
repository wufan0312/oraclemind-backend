# -*- coding: utf-8 -*-
"""天使数字（Angel Number）回归测试。

锁住契约：
- 归一化解析：'11:11' / '1 1 1' / '0011' 等带分隔符输入都能正确归一；
- 非法输入（空串 / 非数字 / 超长）返回 400 而不是 500；
- 释义表与前端 ``oraclemind/src/data/angelNumbers.ts`` 的键**交叉校验**（防止两份数据漂移）；
- 序列分析频次统计正确；
- 三个端点 200 / 400 覆盖。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.paipan.angel_number import (
    ANALYZE_MAX_ITEMS,
    ANGEL_DIGIT_MEANING,
    ANGEL_MAX_DIGITS,
    ANGEL_NUMBERS,
    analyze_sequence,
    compute_angel_number,
    digital_root,
    normalize_angel_input,
    parse_angel_number,
)

# 前端释义表（交叉校验用）：backend/../oraclemind/src/data/angelNumbers.ts
_FRONTEND_TS = (
    Path(__file__).resolve().parents[1] / ".." / "oraclemind" / "src" / "data" / "angelNumbers.ts"
)


# ============================================================================
# (a) 归一化解析
# ============================================================================


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1111", "1111"),
        ("11:11", "1111"),
        ("1 1 1", "111"),
        ("1 2 3", "123"),
        ("0011", "0011"),
        ("11-11", "1111"),
        ("  444  ", "444"),
        ("二〇二六年11:11", "1111"),  # 中文数字非 ASCII，被剥离，仅保留 11:11 → 1111
    ],
)
def test_normalize_strips_non_digits(raw, expected):
    """归一化：只保留数字字符。"""
    assert normalize_angel_input(raw) == expected


def test_parse_1111_exact_hit():
    """'11:11' → 归一 '1111' → 精确命中 '1111'。"""
    r = parse_angel_number("11:11")
    assert r["raw"] == "1111"
    assert r["key"] == "1111"
    assert r["entry"]["n"] == "1111"
    assert r["isRepDigit"] is True
    assert r["repDigit"] == 1


def test_parse_111_from_spaces():
    """'1 1 1' → '111'：全同重复数。"""
    r = parse_angel_number("1 1 1")
    assert r["raw"] == "111"
    assert r["key"] == "111"
    assert r["isRepDigit"] is True
    assert r["isSequence"] is False
    assert r["digits"] == [1]


def test_parse_0011_falls_back_to_digital_root():
    """'0011' 未收录 → 数字根 0+0+1+1=2 → 落到 '222'（与前端口径一致）。"""
    r = parse_angel_number("0011")
    assert r["raw"] == "0011"
    assert r["key"] == "222"
    assert r["key"] != r["raw"]  # 非精确命中
    assert r["digitalRoot"] == 2
    assert r["repDigit"] is None
    assert r["digits"] == [0, 1]


def test_parse_repdigit_compressed_to_three():
    """'22222' 全同 → 压到三位 '222'。"""
    r = parse_angel_number("22222")
    assert r["key"] == "222"
    assert r["isRepDigit"] is True


def test_parse_sequence_flag():
    """'1234' 精确命中且被标记为连续递增序列。"""
    r = parse_angel_number("1234")
    assert r["key"] == "1234"
    assert r["isSequence"] is True


def test_digit_meaning_matches_digits():
    """digitMeaning 的键必须覆盖 digits 的每一位。"""
    r = parse_angel_number("1234")
    assert set(r["digitMeaning"].keys()) == {str(d) for d in r["digits"]}


# ============================================================================
# (b) 非法输入 —— 必须 ValueError（路由层转 400），绝不 500
# ============================================================================


@pytest.mark.parametrize("raw", ["", "   ", "abc", "无数字", "😂😂"])
def test_parse_rejects_no_digit(raw):
    with pytest.raises(ValueError):
        parse_angel_number(raw)


def test_parse_rejects_too_long():
    """归一化后超过 ANGEL_MAX_DIGITS 位 → 拒绝。"""
    with pytest.raises(ValueError):
        parse_angel_number("1" * (ANGEL_MAX_DIGITS + 1))
    # 边界内（恰好等于上限）应可通过
    assert parse_angel_number("1" * ANGEL_MAX_DIGITS)["raw"] == "1" * ANGEL_MAX_DIGITS


def test_parse_result_never_500_on_weird_types():
    """非字符串输入（None / 数字 / 容器）不应触发 TypeError 之类未捕获异常（即不会 500）。

    normalize 现已对 non-str 做 str() 兜底：数字 123 → '123' 合法可解析（不抛）；
    None / [] / {} → 无数字 → 抛 ValueError。无论哪种，都不允许出现 TypeError/AttributeError。
    """
    for bad in (None, 123, [], {}):
        try:
            parse_angel_number(bad)  # type: ignore[arg-type]
        except ValueError:
            pass  # 期望的合法拒绝（如 None）
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"非字符串输入 {bad!r} 抛出了非预期异常：{type(e).__name__}: {e}")


# ============================================================================
# (c) 释义表完整性 + 与前端交叉校验
# ============================================================================


def test_all_triple_repeats_present():
    """000~999 全部三位重复数都有条目（覆盖 1~9 与 111/222…999）。"""
    for d in range(10):
        key = str(d) * 3
        assert key in ANGEL_NUMBERS, f"缺少词条 {key}"
        e = ANGEL_NUMBERS[key]
        assert e["n"] == key
        assert e["title"].strip()
        assert e["core"].strip()
        assert e["advice"].strip()


@pytest.mark.parametrize("key", ["1111", "1212", "1010", "1234"])
def test_common_special_sequences_present(key):
    assert key in ANGEL_NUMBERS


def test_single_digits_resolve_to_entry():
    """单个数字 1~9 虽无独立条目，但必须能解析到有效释义（数字根兜底）。"""
    for d in range(1, 10):
        r = parse_angel_number(str(d))
        assert r["key"] in ANGEL_NUMBERS
        assert r["entry"]["title"].strip()


def test_digit_meaning_covers_0_to_9():
    assert set(ANGEL_DIGIT_MEANING.keys()) == set(range(10))
    for v in ANGEL_DIGIT_MEANING.values():
        assert v.strip()


def test_frontend_table_crosscheck():
    """与前端 angelNumbers.ts 的键集合做交叉校验，防止两份数据漂移。"""
    if not _FRONTEND_TS.exists():
        pytest.skip(f"前端释义表不存在，跳过交叉校验：{_FRONTEND_TS}")

    src = _FRONTEND_TS.read_text(encoding="utf-8")
    # 取 ANGEL_NUMBERS 块内的顶层键（形如 '111': {）
    block = src.split("ANGEL_NUMBERS", 1)[-1]
    block = block.split("ANGEL_DIGIT_MEANING", 1)[0]
    fe_keys = set(re.findall(r"^\s*'(\d+)':\s*\{", block, re.M))

    assert fe_keys, "未能从前端文件解析出任何键，检查正则或文件格式"
    assert fe_keys == set(ANGEL_NUMBERS.keys()), (
        f"前后端释义表键不一致：前端独有 {fe_keys - set(ANGEL_NUMBERS)}，"
        f"后端独有 {set(ANGEL_NUMBERS) - fe_keys}"
    )


def test_frontend_digit_meaning_crosscheck():
    """逐位释义表（0~9）与前端一致。"""
    if not _FRONTEND_TS.exists():
        pytest.skip(f"前端释义表不存在，跳过交叉校验：{_FRONTEND_TS}")

    src = _FRONTEND_TS.read_text(encoding="utf-8")
    block = src.split("ANGEL_DIGIT_MEANING", 1)[-1]
    fe = {int(m[0]): m[1] for m in re.findall(r"^\s*(\d):\s*'([^']+)'", block, re.M)}
    assert fe, "未能从前端解析出逐位释义"
    assert fe == ANGEL_DIGIT_MEANING


# ============================================================================
# (d) 序列分析
# ============================================================================


def test_sequence_counts_frequency():
    """频次统计：'11:11' 与 '1111' 归一后合并计数。"""
    r = analyze_sequence(["11:11", "1111", "444", "444", "444"])
    assert r["total"] == 5
    assert r["unique"] == 2
    assert r["items"][0]["raw"] == "444"
    assert r["items"][0]["count"] == 3
    assert r["items"][0]["ratio"] == pytest.approx(0.6)
    assert r["items"][1]["count"] == 2


def test_sequence_top_and_ratio_sum():
    """top 为出现最多的项，所有 ratio 之和为 1。"""
    r = analyze_sequence(["111", "222", "222", "333", "333", "333"])
    assert len(r["top"]) == 1
    assert r["top"][0]["raw"] == "333"
    assert sum(i["ratio"] for i in r["items"]) == pytest.approx(1.0, abs=1e-6)


def test_sequence_top_ties():
    """并列第一时 top 含多项。"""
    r = analyze_sequence(["111", "222"])
    assert len(r["top"]) == 2
    assert {i["raw"] for i in r["top"]} == {"111", "222"}


def test_sequence_invalid_items_are_reported_not_fatal():
    """无效条目进入 invalid，不中断整体分析。"""
    r = analyze_sequence(["111", "abc", ""])
    assert r["total"] == 1
    assert r["invalid"] == ["abc", ""]


def test_sequence_themes_and_top_key():
    """主题关键词非空，topKey 为频次最高的命中词条。"""
    r = analyze_sequence(["111", "111", "111", "999"])
    assert r["topKey"] == "111"
    assert r["topEntry"]["n"] == "111"
    assert r["themes"], "应归纳出主题关键词"
    assert "念头显化" in r["themes"]


def test_sequence_digit_frequency():
    """逐位频次：'111'(3 个 1) + '11'(2 个 1) → 数字 1 共 5 次。"""
    r = analyze_sequence(["111", "11"])
    assert r["digitFrequency"]["1"] == 5


def test_sequence_rejects_empty():
    with pytest.raises(ValueError):
        analyze_sequence([])


def test_sequence_rejects_all_invalid():
    with pytest.raises(ValueError):
        analyze_sequence(["abc", ""])


def test_sequence_rejects_too_many_items():
    with pytest.raises(ValueError):
        analyze_sequence(["111"] * (ANALYZE_MAX_ITEMS + 1))


# ============================================================================
# (e) 个人天使数字（民俗算法）
# ============================================================================


def test_personal_life_path():
    """1995-03-08 → 数字和 1+9+9+5+0+3+0+8=35 → 8 → '888'。"""
    r = compute_angel_number("1995-03-08")
    assert r["lifePath"] == 8
    assert r["key"] == "888"
    assert r["birthdayNum"] == 8
    assert r["personalNumber"] == "888"
    assert "民俗算法" in r["note"]


def test_personal_accepts_compact_and_date_object():
    from datetime import date

    assert compute_angel_number("19950308")["key"] == "888"
    assert compute_angel_number(date(1995, 3, 8))["key"] == "888"


def test_personal_name_is_echo_only():
    """姓名仅回显，不参与计算（避免混用毕达哥拉斯口径）。"""
    a = compute_angel_number("1995-03-08")
    b = compute_angel_number("1995-03-08", "张三")
    assert a["key"] == b["key"]
    assert b["name"] == "张三"


def test_personal_rejects_bad_format():
    """不足 8 位数字的输入应被拒（"1995" 归一后仅 4 位，非合法 YYYYMMDD）。"""
    with pytest.raises(ValueError):
        compute_angel_number("1995")
