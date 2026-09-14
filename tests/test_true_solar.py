"""真太阳时校正 —— 单元测试 + 八字/紫微接入回归（P3-2）。

校验口径：
  (a) 公式：经度差 (lng−120)×4 + EoT，含跨日；
  (b) 边界：经度缺失 / 越界 / 时辰不详 → 一律返回 None（静默降级，不抛异常）；
  (c) 接入：apply_true_solar 就地改写请求，并经 /api/v1/bazi/paipan 端到端回传 trueSolarTime；
  (d) 一致性：与前端 src/lib/trueSolarTime.ts 同公式（乌鲁木齐应后移约 2 小时，时辰必变）。
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.schemas.paipan import PaipanRequest, apply_true_solar
from app.services.paipan.true_solar import (
    BASE_LONGITUDE,
    LNG_MAX,
    LNG_MIN,
    SHICHEN_MID_HOUR,
    compute_true_solar,
    day_of_year,
    equation_of_time,
    shichen_to_hour,
)

# ===== (a) 公式 =====


def test_day_of_year():
    assert day_of_year(2026, 1, 1) == 1
    assert day_of_year(2026, 12, 31) == 365
    assert day_of_year(2024, 12, 31) == 366  # 闰年


def test_eot_range_and_known_sign():
    """EoT 全年在 ±20 分钟内；2 月最慢（负）、11 月最快（正）。"""
    vals = [equation_of_time(2026, m, 15) for m in range(1, 13)]
    assert all(-20 < v < 20 for v in vals), vals
    assert equation_of_time(2026, 2, 15) < 0    # 2 月真太阳时偏慢
    assert equation_of_time(2026, 11, 15) > 0   # 11 月偏快


def test_longitude_correction_sign():
    """偏东（上海 121.5）加正、偏西（乌鲁木齐 87.6）加负。"""
    east = compute_true_solar(2026, 6, 21, 12, 0, 121.5)
    west = compute_true_solar(2026, 6, 21, 12, 0, 87.6)
    assert east["longitudeMin"] == pytest.approx((121.5 - BASE_LONGITUDE) * 4)
    assert west["longitudeMin"] == pytest.approx((87.6 - BASE_LONGITUDE) * 4)
    assert east["longitudeMin"] > 0 > west["longitudeMin"]


def test_urumqi_shifts_time_back_about_two_hours():
    """乌鲁木齐比北京时间晚约 2 小时 —— 时辰必然改变，这是接入的核心价值。"""
    r = compute_true_solar(2026, 6, 21, 14, 0, 87.6)
    # 经度差 (87.6−120)×4 = −129.6 分；6 月 EoT 约 −1.7 分 → 合计约 −131 分
    assert -140 < r["totalMin"] < -120
    assert r["hour"] == 11          # 14:00 − 约 2:11 → 11:48
    assert 47 <= r["minute"] <= 49


def test_day_rollover_forward_and_back():
    """23:40 偏东 → 次日；00:10 偏西 → 前一日。"""
    fwd = compute_true_solar(2026, 3, 15, 23, 40, 130.0)
    assert fwd["dayOffset"] == 1
    assert (fwd["year"], fwd["month"], fwd["day"]) == (2026, 3, 16)

    back = compute_true_solar(2026, 3, 15, 0, 10, 80.0)
    assert back["dayOffset"] == -1
    assert (back["year"], back["month"], back["day"]) == (2026, 3, 14)


def test_matches_frontend_formula():
    """与前端 src/lib/trueSolarTime.ts 逐项对齐，防止前后端漂移。"""
    y, m, d, hh, mm, lng = 2026, 9, 10, 8, 30, 116.4

    # 前端实现（原样复刻，作为独立参照）
    start = date(y, 1, 1).toordinal()
    n = date(y, m, d).toordinal() - start + 1
    b = (2 * math.pi * (n - 81)) / 365
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    r = compute_true_solar(y, m, d, hh, mm, lng)
    assert r["longitudeMin"] == pytest.approx(round((lng - 120) * 4, 2), abs=0.01)
    assert r["eotMin"] == pytest.approx(round(eot, 2), abs=0.01)
    assert r["clockTime"] == "08:30"


# ===== (b) 边界：一律静默降级 =====


@pytest.mark.parametrize("lng", [None, "abc", 0.0, 72.9, 135.1, 200.0, -180.0])
def test_invalid_longitude_returns_none(lng):
    assert compute_true_solar(2026, 6, 1, 12, 0, lng) is None


@pytest.mark.parametrize(
    "time_text,expect",
    [("子时", 0), ("丑时", 2), ("午时", 12), ("亥时", 22), ("不详", None), ("", None), (None, None)],
)
def test_shichen_to_hour(time_text, expect):
    assert shichen_to_hour(time_text) == expect


def test_shichen_table_covers_all_twelve():
    assert len(SHICHEN_MID_HOUR) == 12
    assert sorted(SHICHEN_MID_HOUR.values()) == list(range(0, 24, 2))


def test_invalid_date_returns_none():
    assert compute_true_solar(2026, 2, 30, 12, 0, 116.4) is None


# ===== (c) 接入：apply_true_solar =====


def test_apply_true_solar_mutates_request_in_place():
    req = PaipanRequest(year=2026, month=6, day=21, hour=14, minute=0, longitude=87.6)
    info = apply_true_solar(req)
    assert info is not None
    # 请求本体已被改写为校正后时刻（缓存键也随之一致）
    assert (req.year, req.month, req.day, req.hour) == (
        info["year"], info["month"], info["day"], info["hour"]
    )
    assert req.hour == 11


def test_apply_true_solar_derives_hour_from_time_text():
    """没给 hour 时从 timeText 折算（区间中点），与排盘服务同表。"""
    req = PaipanRequest(year=2026, month=6, day=21, timeText="午时", longitude=87.6)
    info = apply_true_solar(req)
    assert info is not None
    assert info["clockTime"] == "12:00"
    assert req.hour == 9  # 午时中点 12:00 − 约 2:11


def test_apply_true_solar_noop_without_longitude():
    """没有经度 → 完全不动请求（零风险默认）。"""
    req = PaipanRequest(year=2026, month=6, day=21, hour=14)
    assert apply_true_solar(req) is None
    assert (req.year, req.month, req.day, req.hour) == (2026, 6, 21, 14)


def test_apply_true_solar_noop_when_time_unknown():
    """时辰不详 → 不拿假时刻硬算。"""
    req = PaipanRequest(year=2026, month=6, day=21, timeText="不详", longitude=87.6)
    assert apply_true_solar(req) is None
    assert req.hour is None


def test_apply_true_solar_noop_out_of_china():
    req = PaipanRequest(year=2026, month=6, day=21, hour=14, longitude=-70.0)
    assert apply_true_solar(req) is None
    assert req.hour == 14


# ===== (d) 端到端：经 API 回传 =====


def test_bazi_endpoint_returns_true_solar_time():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    base = {"year": 1990, "month": 6, "day": 21, "hour": 14, "gender": "男"}

    without = client.post("/api/v1/bazi/paipan", json=base)
    assert without.status_code == 200
    assert "trueSolarTime" not in without.json()

    with_lng = client.post("/api/v1/bazi/paipan", json={**base, "longitude": 87.6})
    assert with_lng.status_code == 200
    tst = with_lng.json().get("trueSolarTime")
    assert tst is not None
    assert tst["lng"] == 87.6
    assert tst["clockTime"] == "14:00"


def test_same_longitude_is_stable_and_cached():
    """同参数两次请求结果一致（缓存键含校正后时刻，不会串味）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    payload = {"year": 1990, "month": 6, "day": 21, "hour": 14, "gender": "男", "longitude": 87.6}
    a = client.post("/api/v1/bazi/paipan", json=payload).json()
    b = client.post("/api/v1/bazi/paipan", json=payload).json()
    assert a["pillars"] == b["pillars"]
    assert a["trueSolarTime"] == b["trueSolarTime"]


def test_different_longitude_can_change_hour_pillar():
    """不同经度 → 不同时柱（校正真的生效，而不是只回显数字）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    base = {"year": 1990, "month": 6, "day": 21, "hour": 14, "gender": "男"}
    beijing = client.post("/api/v1/bazi/paipan", json={**base, "longitude": 116.4}).json()
    urumqi = client.post("/api/v1/bazi/paipan", json={**base, "longitude": 87.6}).json()
    assert beijing["pillars"][3]["zhi"] != urumqi["pillars"][3]["zhi"]


def test_ziwei_endpoint_returns_true_solar_time():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/v1/ziwei/paipan",
        json={"year": 1990, "month": 6, "day": 21, "hour": 14, "gender": "男", "longitude": 87.6},
    )
    assert r.status_code == 200
    assert r.json().get("trueSolarTime", {}).get("lng") == 87.6


def test_bounds_constants_sane():
    assert LNG_MIN < BASE_LONGITUDE < LNG_MAX
