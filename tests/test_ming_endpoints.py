"""测字 / 姓名五格 / 合婚 端点测试（P2-4 后端化）。

覆盖：4 个端点的正常返回、参数非法 → 400（而非 500）、与 ceming.ts 同口径交叉校验。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------- 五格剖象 ----------
def test_wuge_ok(client):
    r = client.post(
        "/api/v1/ming/wuge",
        json={"surname": "李", "given": "明轩", "surnameStrokes": [7], "givenStrokes": [8, 10]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["surname"] == "李"
    assert set(body["grids"].keys()) >= {"tian", "ren", "di", "wai", "zong"}
    assert 0 <= body["score"] <= 100
    assert isinstance(body["threeTalent"], dict)


def test_wuge_missing_required_422(client):
    # 缺必填字段 givenStrokes → pydantic 拒绝（422，而非 500）
    r = client.post(
        "/api/v1/ming/wuge",
        json={"surname": "李", "given": "x", "surnameStrokes": [7]},
    )
    assert r.status_code in (400, 422)


# ---------- 合婚（生肖）----------
def test_hehun_ok(client):
    r = client.post(
        "/api/v1/ming/hehun",
        json={"maleZhi": "子", "femaleZhi": "丑", "maleGan": "甲", "femaleGan": "乙"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"relations", "verdict", "level", "score"}
    assert 0 <= body["score"] <= 100
    assert "he" in body["relations"]  # 六合布尔键


def test_hehun_bad_zhi_400(client):
    r = client.post("/api/v1/ming/hehun", json={"maleZhi": "猫", "femaleZhi": "丑"})
    assert r.status_code == 400


# ---------- 八字合婚 ----------
def test_hehun_bazi_ok(client):
    r = client.post(
        "/api/v1/ming/hehun-bazi",
        json={
            "maleDayGan": "甲",
            "femaleDayGan": "己",
            "maleWuxing": {"金": 1, "木": 2, "水": 1, "火": 1, "土": 1},
            "femaleWuxing": {"金": 1, "木": 1, "水": 1, "火": 1, "土": 2},
            "maleZhi": "子",
            "femaleZhi": "丑",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "relations" in body and "score" in body
    assert 0 <= body["score"] <= 100


def test_hehun_bazi_requires_gan(client):
    r = client.post(
        "/api/v1/ming/hehun-bazi",
        json={"maleDayGan": "", "femaleDayGan": "", "maleWuxing": {}, "femaleWuxing": {}},
    )
    # 空日干 → compute_hehun 抛 ValueError → 400（不是 500）
    assert r.status_code == 400


# ---------- 测字 ----------
def test_cezi_ok(client):
    r = client.post("/api/v1/ming/cezi", json={"char": "福", "strokes": 14})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["char"] == "福"
    assert "element" in body and "trigram" in body and "tendency" in body
    assert body["codePoint"] == ord("福")


def test_cezi_too_many_chars_422(client):
    # 5 字超过 max_length=4，应被 pydantic 拒绝（422，而非 500）
    r = client.post("/api/v1/ming/cezi", json={"char": "福禄寿喜财", "strokes": 40})
    assert r.status_code in (400, 422)


# ---------- 与 ceming.ts 同口径交叉校验 ----------
def test_wuge_crosscheck_with_local(client):
    """后端五格与前端 ceming.ts（analyzeWuge 口径）应当一致：用纯函数复算天格数理。"""
    from app.services.paipan.ceming import compute_wuge

    res = compute_wuge([7], [8, 10])
    # 天格 = 姓笔画 + 1（单姓）
    assert res["grids"]["tian"]["num"] == 7 + 1
    # 人格 = 姓末字 + 名首字
    assert res["grids"]["ren"]["num"] == 7 + 8
    # 地格 = 名笔画之和
    assert res["grids"]["di"]["num"] == 8 + 10


def test_hehun_crosscheck_liuhe(client):
    """子丑合（六合）→ relations['he'] 为 True。"""
    from app.services.paipan.ceming import compute_hehun

    res = compute_hehun("子", "丑")
    assert res["relations"]["he"] is True
    assert res["level"] in ("上吉", "吉", "平", "凶")
