# -*- coding: utf-8 -*-
"""数字命理排盘 · 权威盘 cross-check（对齐 test_qimen_crosscheck 模式）。

数字命理为纯算术（无历法/天文依赖），故可完全独立复算：
1. 对照常量表（字母→数值 LETTER_VALUE、生命灵数/流年/数字解读完整性）。
2. 独立复算 digital_root / 九宫格 / 生命灵数 / 流年 / 挑战数 / 姓名数，
   与被测输出逐字段比对 —— 抓"接线"类 bug（取错字段、化简规则写反、漏算）。

不依赖"今天"：compute_num 显式传入 today 固定流年基准。
"""
from datetime import date

from app.services.paipan.numerology import (
    CHALLENGE_DATA, NUM_COLORS, NUM_DETAILS, YEAR_MEANINGS,
    LETTER_VALUE, VOWELS, compute_challenge, compute_num,
    digital_root, num_grid_counts,
)
from app.services.paipan.pinyin_data import hanzi_to_pinyin

# ===== 1) 字母→数值表（毕达哥拉斯：A=1…I=9 循环）=====
EXPECT_LETTER_VALUE = {
    c: (i % 9) + 1 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
}


def test_letter_value_table():
    assert LETTER_VALUE == EXPECT_LETTER_VALUE, LETTER_VALUE
    # 元音集合（Y 归辅音）
    assert VOWELS == frozenset("aeiou")


def test_data_table_integrity():
    """生命灵数/流年/颜色/挑战数 常量表键完整。"""
    assert set(NUM_DETAILS) == set(range(1, 10)) | {11, 22, 33}, set(NUM_DETAILS)
    assert set(YEAR_MEANINGS) == set(range(1, 10))
    assert set(NUM_COLORS) == set(range(1, 10)) | {11, 22, 33}
    assert set(CHALLENGE_DATA) == set(range(0, 9))


# ===== 2) 独立复算原语 =====
def _oracle_digital_root(n: int, keep_master: bool = False) -> int:
    while n > 9:
        if keep_master and n in (11, 22, 33):
            return n
        n = sum(int(c) for c in str(n))
    if keep_master and n in (11, 22, 33):
        return n
    return n


def _oracle_num_grid(year: int, month: int, day: int) -> dict:
    s = f"{year}{month}{day}"
    counts = {i: 0 for i in range(1, 10)}
    for ch in s:
        if "1" <= ch <= "9":
            counts[int(ch)] += 1
    return counts


def _oracle_life_path(year: int, month: int, day: int) -> int:
    return _oracle_digital_root(year + month + day, keep_master=True)


def _oracle_years(year: int, month: int, day: int, now: int) -> list[dict]:
    out = []
    for i in range(9):
        yr = now + i
        digit_sum = month + day + sum(int(c) for c in str(yr))
        py = _oracle_digital_root(digit_sum)
        out.append({"yr": yr, "py": py,
                    "tag": YEAR_MEANINGS[py].split("：")[0],
                    "isCurrent": i == 0})
    return out


def _oracle_challenge(year: int, month: int, day: int) -> dict:
    mo, da, ye = (_oracle_digital_root(month), _oracle_digital_root(day),
                  _oracle_digital_root(year))
    return {"c1": abs(mo - da), "c2": abs(da - ye),
            "c3": abs(abs(mo - da) - abs(da - ye)), "c4": abs(mo - ye)}


def _oracle_name(name: str, life_path: int):
    py = hanzi_to_pinyin(name.strip())
    letters = [c for c in py.text.lower() if c.isascii() and c.isalpha()]
    if not letters:
        return None
    def total(pred):
        return sum(LETTER_VALUE[c.upper()] for c in letters if pred(c))
    expression = _oracle_digital_root(total(lambda c: True), keep_master=True)
    soul = _oracle_digital_root(total(lambda c: c in VOWELS), keep_master=True)
    pers = _oracle_digital_root(total(lambda c: c not in VOWELS), keep_master=True)
    return {
        "pinyin": py.text,
        "expression": expression,
        "soulUrge": soul,
        "personality": pers,
        "maturity": _oracle_digital_root(life_path + expression, keep_master=True),
    }


def test_digital_root_known():
    """数字根化简（含大师数保留）须与独立复算一致。"""
    cases = [
        (1995, False, 6), (0, False, 0), (9, False, 9), (19, False, 1),
        (123456789, False, 9), (1990, False, 1),
        (11, True, 11), (22, True, 22), (33, True, 33),
        (29, True, 11), (38, True, 11), (29, False, 2),
        (2010, True, 3), (2010, False, 3),
    ]
    for n, km, exp in cases:
        assert digital_root(n, km) == exp, (n, km, digital_root(n, km), exp)
        assert digital_root(n, km) == _oracle_digital_root(n, km)


def test_num_grid_known():
    """九宫格统计须与独立复算一致。"""
    for y, m, d in [(1990, 5, 15), (1987, 6, 12), (2000, 2, 29), (1995, 11, 23)]:
        assert num_grid_counts(y, m, d) == _oracle_num_grid(y, m, d)
        miss = sorted(k for k, v in _oracle_num_grid(y, m, d).items() if v == 0)
        r = compute_num(y, m, d, today=date(2026, 1, 1))
        assert r["missing"] == miss, (y, m, d, r["missing"], miss)


def test_life_path_and_birthday():
    """生命灵数 / 生日数须与独立复算一致。"""
    for y, m, d in [(1990, 5, 15), (1987, 6, 12), (2000, 2, 29), (1995, 11, 23)]:
        r = compute_num(y, m, d, today=date(2026, 1, 1))
        assert r["lifePath"] == _oracle_life_path(y, m, d)
        assert r["birthdayNum"] == _oracle_digital_root(d, keep_master=True)


def test_years_flow():
    """未来 9 年流年数字/主题/当前标记须与独立复算一致。"""
    now = 2026
    for y, m, d in [(1990, 5, 15), (1987, 6, 12), (2000, 2, 29)]:
        r = compute_num(y, m, d, today=date(now, 1, 1))
        oracle = _oracle_years(y, m, d, now)
        out = [{"yr": x["yr"], "py": x["py"], "tag": x["tag"], "isCurrent": x["isCurrent"]}
               for x in r["years"]]
        assert out == oracle, (y, m, d, out, oracle)


def test_challenge_numbers():
    """四挑战数须与独立复算一致。"""
    for y, m, d in [(1990, 5, 15), (1987, 6, 12), (2000, 2, 29), (1995, 11, 23)]:
        r = compute_num(y, m, d, today=date(2026, 1, 1))
        exp = _oracle_challenge(y, m, d)
        assert r["core"]["challenge"] == exp, (y, m, d, r["core"]["challenge"], exp)


def test_name_numbers():
    """姓名表现/内驱/人格/成熟数须与独立复算一致（拼音转写用同一工具）。"""
    for name in ["张三", "李四", "王小红"]:
        life_path = _oracle_life_path(1990, 5, 15)
        r = compute_num(1990, 5, 15, today=date(2026, 1, 1), name=name)
        o = _oracle_name(name, life_path)
        if o is None:  # 拼音无法转写则跳过数值比对
            assert r["core"]["expression"] is None
            continue
        core = r["core"]
        assert core["pinyin"] == o["pinyin"]
        assert core["expression"] == o["expression"], (name, core["expression"], o["expression"])
        assert core["soulUrge"] == o["soulUrge"]
        assert core["personality"] == o["personality"]
        assert core["maturity"] == o["maturity"]


def test_no_name_core_only_challenge():
    """无姓名时核心数仅含挑战数，姓名三项为 None。"""
    r = compute_num(1990, 5, 15, today=date(2026, 1, 1))
    core = r["core"]
    assert core["expression"] is None and core["soulUrge"] is None
    assert core["personality"] is None and core["maturity"] is None
    assert "challenge" in core and core["challenge"]["c1"] >= 0
