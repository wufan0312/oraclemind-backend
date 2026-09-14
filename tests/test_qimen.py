# -*- coding: utf-8 -*-
"""奇门遁甲 · 手动定局（Q10）回归测试。

锁住契约：
- 自动定局（manual_ju=None）走拆补法，type 严格等于推算结果；
- 手动定局（manual_ju=(yinyang, ju)）type 严格等于传入值，且地盘/值符值使随之联动重算；
- 手动模式不破坏后续断卦层（九宫/三奇/指南/空亡/马星）。
"""

from app.schemas.paipan import PaipanRequest
from app.services.paipan.qimen import compute_qimen

BASE = dict(year=1995, month=1, day=1, time_text="子时", gender="男")


def test_auto_ju_uses_chaibu():
    """自动定局：冬至后拆补法 → 阳遁7局（锁住当前算法口径）。"""
    r = compute_qimen(**BASE)
    assert r["type"] == "阳遁7局"
    assert r["jieqi"] == "冬至"


def test_manual_ju_yang1_strict():
    """手动阳遁1局：type 与值符值使严格等于传入局数推算。"""
    r = compute_qimen(**BASE, manual_ju=("阳", 1))
    assert r["type"] == "阳遁1局"
    assert r["valueFu"] == "天辅星"
    assert r["valueShi"] == "杜门"


def test_manual_ju_yin6_strict():
    r = compute_qimen(**BASE, manual_ju=("阴", 6))
    assert r["type"] == "阴遁6局"


def test_manual_overrides_auto():
    """手动模式必须与自动路径产生不同定局。"""
    auto = compute_qimen(**BASE)
    manual = compute_qimen(**BASE, manual_ju=("阳", 1))
    assert auto["type"] != manual["type"]
    assert manual["type"] == "阳遁1局"


def test_manual_ju_links_pan():
    """局数不同 → 值符星随定局联动变化（地盘戊起宫变 → 值符宫变）。"""
    a = compute_qimen(**BASE, manual_ju=("阳", 1))
    b = compute_qimen(**BASE, manual_ju=("阳", 9))
    assert a["type"] != b["type"]
    assert a["valueFu"] != b["valueFu"]


def test_manual_ju_still_renders_analysis():
    """手动模式不破坏后续断卦层。"""
    r = compute_qimen(**BASE, manual_ju=("阳", 1))
    assert len(r["palaces"]) == 9
    assert len(r["qi"]) >= 3            # 乙丙丁三奇 + 生门方位
    assert len(r["guide"]) >= 3
    assert r["kongWang"] and r["maStar"]   # 空亡/马星仍计算（不依赖局数）


def test_schema_qimen_ju_roundtrip():
    """请求 schema 正确透传 qimen_ju 字段，缺省为 None（走自动）。"""
    req = PaipanRequest(year=1995, month=1, day=1, timeText="子时", qimen_ju={"yinyang": "阳", "ju": 1})
    assert req.qimen_ju == {"yinyang": "阳", "ju": 1}
    req2 = PaipanRequest(year=1995, month=1, day=1, timeText="子时")
    assert req2.qimen_ju is None
