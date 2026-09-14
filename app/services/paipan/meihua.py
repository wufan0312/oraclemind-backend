# -*- coding: utf-8 -*-
"""梅花易数服务 —— 时间起卦 + 体用生克。

起卦法（与六爻同源的传统时间起卦）：
- 上卦 = (年支数 + 农历月 + 农历日) % 8，余 0 取 8
- 下卦 = (年支数 + 农历月 + 农历日 + 时支数) % 8，余 0 取 8
- 动爻 = 总数 % 6，余 0 取 6

体用规则：动爻在下卦（1-3）则体为上卦、用为下卦；动爻在上卦（4-6）反之。
体用生克：用生体大吉 / 比和吉 / 体克用小吉 / 体生用泄气小凶 / 用克体大凶。

输出与前端 bugua 页 MeihuaModule 数据结构对齐：
benGua / bianGua / huGua / dongYao / ti / yong / tiYong / analysis。
"""

from __future__ import annotations

from lunar_python import Solar

from .yijing_data import (
    GAN_WUXING,
    KE,
    NUM_TRIGRAM,
    SHENG,
    TRIGRAM_MEANING,
    TRIGRAM_NUM,
    TRIGRAM_SYMBOL,
    TRIGRAM_WUXING,
    ZHI_WUXING,
    hexagram_by_upper_lower,
    hexagram_symbol,
    hucuo_zong,
    leixiang_of,
    lines_to_gua,
    trigram_num,
    wang_shuai_of,
    xunkong_of,
)
from .zhouyi_data import gua_ci, yao_ci, yao_title

_ZHI_ORD = {"子": 1, "丑": 2, "寅": 3, "卯": 4, "辰": 5, "巳": 6, "午": 7, "未": 8, "申": 9, "酉": 10, "戌": 11, "亥": 12}

# 八卦卦德（用于断语）
_TRIGRAM_VIRTUE = {
    "乾": "刚健", "兑": "喜悦", "离": "明丽", "震": "奋动", "巽": "谦入", "坎": "险陷", "艮": "静止", "坤": "柔顺",
}


def _time_to_hour(time_text: str) -> int:
    mapping = {
        "子时": 0, "丑时": 2, "寅时": 4, "卯时": 6, "辰时": 8, "巳时": 10,
        "午时": 12, "未时": 14, "申时": 16, "酉时": 18, "戌时": 20, "亥时": 22,
    }
    for k, v in mapping.items():
        if time_text.startswith(k):
            return v
    return 12


def _qigua(year: int, month: int, day: int, hour: int | None, time_text: str) -> dict:
    h = hour if hour is not None else 12
    if time_text and hour is None:
        h = _time_to_hour(time_text)
    lunar = Solar.fromYmdHms(year, month, day, h, 0, 0).getLunar()
    y_z = _ZHI_ORD.get(lunar.getYearZhi(), 1)
    m, d = lunar.getMonth(), lunar.getDay()
    t_z = _ZHI_ORD.get(lunar.getTimeZhi(), 1)
    total = y_z + m + d
    total2 = total + t_z
    return {
        "shang": total % 8 or 8,
        "xia": total2 % 8 or 8,
        "dong": total2 % 6 or 6,
        "calc": f"{y_z}+{m}+{d}={total}→{total % 8}；+{t_z}={total2}→{total2 % 8}、余{total2 % 6}",
        "lunar": lunar.toString(),
        "timeZhi": lunar.getTimeZhi(),
    }


# ============================ 起卦法（M5） ============================
# 先天卦数：乾1兑2离3震4巽5坎6艮7坤8
_XIANTIAN_NUM = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}
# 先天卦数取卦：%8 余 0 取 8
_NUM_TO_TRIGRAM = {v: k for k, v in _XIANTIAN_NUM.items()}


def _num_to_trigram(n: int) -> str:
    """数字 -> 卦（先天数 %8，余 0 取 8）。"""
    return _NUM_TO_TRIGRAM[n % 8 or 8]


def _build_qigua_result(shang_num: int, xia_num: int, dong: int, calc: str,
                        lunar_text: str, time_zhi: str, method: str) -> dict:
    """统一构造起卦结果 dict。dong 会归一到 1..6。"""
    d = dong % 6 or 6
    return {
        "shang": shang_num % 8 or 8,
        "xia": xia_num % 8 or 8,
        "dong": d,
        "calc": calc,
        "lunar": lunar_text,
        "timeZhi": time_zhi,
        "method": method,
    }


def _qigua_by_numbers(n1: int, n2: int, lunar_text: str = "",
                      time_zhi: str = "") -> dict:
    """数字起卦：上卦=n1%8、下卦=n2%8、动爻=(n1+n2)%6。"""
    return _build_qigua_result(
        n1 % 8 or 8, n2 % 8 or 8, (n1 + n2) % 6 or 6,
        f"数字起卦：{n1}÷8余{n1 % 8 or 8}→上卦；{n2}÷8余{n2 % 8 or 8}→下卦；"
        f"({n1}+{n2})÷6余{(n1 + n2) % 6 or 6}→动爻",
        lunar_text, time_zhi, "number",
    )


def _qigua_by_text(text: str, lunar_text: str = "", time_zhi: str = "") -> dict:
    """字数起卦：平分两段，前段字数取上卦、后段字数取下卦，总字数取动爻。

    字数为 1 时按 1 计；未输入则退回 1/1。
    """
    t = (text or "").strip()
    if not t:
        return _qigua_by_numbers(1, 1, lunar_text, time_zhi)
    n = len(t)
    half = n // 2
    a, b = (n, 0) if n == 1 else (half if half else 1, n - half if n - half else 1)
    return _build_qigua_result(
        a % 8 or 8, b % 8 or 8, n % 6 or 6,
        f"字数起卦：「{t}」共{n}字，分上下 {a}/{b}；{a}÷8余{a % 8 or 8}→上卦、"
        f"{b}÷8余{b % 8 or 8}→下卦；{n}÷6余{n % 6 or 6}→动爻",
        lunar_text, time_zhi, "text",
    )


def _qigua_manual(shang: int, xia: int, dong: int, lunar_text: str = "",
                  time_zhi: str = "") -> dict:
    """手动指定：直接给上卦数/下卦数/动爻（1-8, 1-8, 1-6）。"""
    return _build_qigua_result(
        shang, xia, dong,
        f"手动指定：上卦数{shang}、下卦数{xia}、动爻第{dong}爻",
        lunar_text, time_zhi, "manual",
    )


def _gua_view(name: str) -> dict:
    """八卦 -> 视图对象（含万物类象 leiXiang，M3）。"""
    return {
        "name": name,
        "symbol": TRIGRAM_SYMBOL[name],
        "num": TRIGRAM_NUM[name],
        "wuxing": TRIGRAM_WUXING[name],
        "meaning": TRIGRAM_MEANING[name],
        "virtue": _TRIGRAM_VIRTUE[name],
        "leiXiang": leixiang_of(name),
    }


def _hexa_view(hexagram: dict, symbol: str, tag: str) -> dict:
    return {
        "name": hexagram["name"],
        "symbol": symbol,
        "desc": hexagram["desc"],
        "gong": hexagram["gong"],
        "upper": _gua_view(hexagram["upper"]),
        "lower": _gua_view(hexagram["lower"]),
        "tag": tag,
    }


def _tiyong(liang: tuple[str, str, int]) -> tuple[str, str, str]:
    """(上卦, 下卦, 动爻) -> (体卦, 用卦, 关系)。"""
    shang, xia, dong = liang
    if dong <= 3:  # 下卦动 -> 体为上卦、用为下卦
        return shang, xia, "下卦动"
    return xia, shang, "上卦动"


def compute_meihua(year: int, month: int, day: int, hour: int | None = None,
                   gender: str = "男", time_text: str = "", question: str = "",
                   method: str = "time", num1: int | None = None, num2: int | None = None,
                   shang_num: int | None = None, xia_num: int | None = None,
                   dong_num: int | None = None, num_type: str = "xian") -> dict:
    """梅花易数起卦排盘。

    method：time 时间起卦（默认）/ number 数字起卦 / text 字数起卦 / manual 手动指定。
    - number：num1、num2 两个报数
    - text：以 question 的字数起卦
    - manual：shang_num(1-8)、xia_num(1-8)、dong_num(1-6)
    """
    # --- M5：按起卦法分发 ---
    base = _qigua(year, month, day, hour, time_text)  # 用于取农历/时支等元信息
    if method == "number" and num1 is not None:
        qg = _qigua_by_numbers(int(num1), int(num2 or num1), base["lunar"], base["timeZhi"])
    elif method == "text":
        qg = _qigua_by_text(question, base["lunar"], base["timeZhi"])
    elif method == "manual" and shang_num is not None:
        qg = _qigua_manual(int(shang_num), int(xia_num or 1), int(dong_num or 1),
                           base["lunar"], base["timeZhi"])
    else:
        qg = base
    shang_gua = NUM_TRIGRAM[qg["shang"]]
    xia_gua = NUM_TRIGRAM[qg["xia"]]
    dong = qg["dong"]

    ben = hexagram_by_upper_lower(shang_gua, xia_gua)
    if ben is None:
        raise ValueError("无法匹配卦象（起卦数据异常）")
    ben_view = _hexa_view(ben, hexagram_symbol(shang_gua, xia_gua), "本卦")

    # 变卦
    from .yijing_data import gua_to_lines
    bits = gua_to_lines(ben)
    flipped = list(bits)
    flipped[dong - 1] = not flipped[dong - 1]
    b_shang, b_xia = lines_to_gua(flipped)
    bian = hexagram_by_upper_lower(b_shang, b_xia)
    bian_view = _hexa_view(bian, hexagram_symbol(b_shang, b_xia), "变卦") if bian else None

    # 互卦：本卦 2/3/4 爻为下互、3/4/5 爻为上互
    from .yijing_data import gua_to_lines
    bits = gua_to_lines(ben)
    low3, up3 = tuple(bits[1:4]), tuple(bits[2:5])
    # 互卦 = 下互(下卦) + 上互(上卦)
    h_shang, h_lower = lines_to_gua(list(low3) + list(up3))
    hu = hexagram_by_upper_lower(h_shang, h_lower)
    hu_view = None
    if hu:
        hu_view = {
            "name": hu["name"],
            "symbol": hexagram_symbol(h_shang, h_lower),
            "desc": hu["desc"],
            "upper": _gua_view(h_shang),
            "lower": _gua_view(h_lower),
        }

    # --- M7：错卦 / 综卦（复用 yijing_data.hucuo_zong，helper 现成直接调） ---
    cuo_view = zong_view = None
    hcz = hucuo_zong(gua_to_lines(ben))
    cuo = hexagram_by_upper_lower(*hcz["cuo"])
    zong = hexagram_by_upper_lower(*hcz["zong"])
    if cuo:
        cuo_view = {
            "name": cuo["name"], "symbol": hexagram_symbol(*hcz["cuo"]), "desc": cuo["desc"],
            "upper": _gua_view(hcz["cuo"][0]), "lower": _gua_view(hcz["cuo"][1]),
        }
    if zong:
        zong_view = {
            "name": zong["name"], "symbol": hexagram_symbol(*hcz["zong"]), "desc": zong["desc"],
            "upper": _gua_view(hcz["zong"][0]), "lower": _gua_view(hcz["zong"][1]),
        }

    # --- M4：卦辞 / 动爻爻辞 ---
    ben_view["guaCi"] = gua_ci(ben["name"])
    if bian_view:
        bian_view["guaCi"] = gua_ci(bian["name"])
    if hu_view:
        hu_view["guaCi"] = gua_ci(hu["name"])
    # 动爻爻辞：本卦动爻位的阴阳决定爻题（九/六）
    dong_yang = bool(bits[qing_dong_idx]) if (qing_dong_idx := dong - 1) >= 0 else True
    dong_yao_title = yao_title(dong, dong_yang)
    dong_yao_ci = yao_ci(ben["name"], dong_yao_title)

    # --- M1：体用旺衰（月令 + 日辰） ---
    _lunar = Solar.fromYmdHms(year, month, day,
                              hour if hour is not None else 12, 0, 0).getLunar()
    month_zhi = _lunar.getMonthZhi()
    day_gan, day_zhi = _lunar.getDayGan(), _lunar.getDayZhi()
    day_wx = GAN_WUXING.get(day_gan, "土")
    xk1, xk2 = xunkong_of(day_gan, day_zhi)

    # 体用
    ti_name, yong_name, dong_note = _tiyong((shang_gua, xia_gua, dong))
    ti, yong = _gua_view(ti_name), _gua_view(yong_name)
    relation, ji_raw, ji_desc = _shengke(ti["wuxing"], yong["wuxing"])

    ti_wang = _wangshuai_view(ti["name"], ti["wuxing"], month_zhi, day_wx)
    yong_wang = _wangshuai_view(yong["name"], yong["wuxing"], month_zhi, day_wx)
    # 体衰减吉、体旺增吉
    _, ji = _adjust_ji_by_wang(relation, ji_raw, ti_wang["strength"])
    ji_adjusted = (ji != ji_raw)
    # 体/用是否落旬空（体空则事虚）
    ti_wx_zhi_empty = {ti["wuxing"]} & {ZHI_WUXING.get(xk1, ""), ZHI_WUXING.get(xk2, "")}
    ti_empty = bool(ti_wx_zhi_empty)
    yong_wx_zhi_empty = {yong["wuxing"]} & {ZHI_WUXING.get(xk1, ""), ZHI_WUXING.get(xk2, "")}
    yong_empty = bool(yong_wx_zhi_empty)

    # --- M9：体用互变四卦关系矩阵（体↔用/互/变 + 用↔变） ---
    relation_matrix = _relation_matrix(ti, yong, hu_view, bian_view, dong)

    # --- M2：应期推断（梅花招牌：数取先天/后天 + 旺衰定迟速 + 月令定时令 + 互变参断） ---
    yingqi = _yingqi_meihua(shang_gua, xia_gua, dong, ti, yong, hu_view, bian_view,
                            ti_wang, yong_wang, month_zhi, day_gan, day_zhi, num_type)

    # 断语
    analysis = _analysis_text(ben, bian, hu, ti, yong, relation, dong, question,
                              ti_wang, yong_wang, ji, ji_raw, ji_adjusted,
                              dong_yao_title, dong_yao_ci, yingqi)

    return {
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": qg["lunar"],
        "timeText": time_text or ("不详" if hour is None else f"{hour}时"),
        "qigua": qg["calc"],
        "method": qg.get("method", "time"),
        "benGua": ben_view,
        "bianGua": bian_view,
        "huGua": hu_view,
        "cuoGua": cuo_view,        # M7 错卦（阴阳全反）
        "zongGua": zong_view,      # M7 综卦（上下翻转）
        "dongYao": dong,
        "dongYaoTitle": dong_yao_title,
        "dongYaoCi": dong_yao_ci,
        "ti": ti,
        "yong": yong,
        "tiWang": ti_wang,
        "yongWang": yong_wang,
        "wangshuai": {
            "monthZhi": month_zhi,
            "dayGan": day_gan,
            "dayZhi": day_zhi,
            "dayWuxing": day_wx,
            "xunkong": f"{xk1}{xk2}",
            "tiEmpty": ti_empty,
            "yongEmpty": yong_empty,
        },
        "tiYong": {
            "relation": relation, "ji": ji, "rawJi": ji_raw,
            "jiAdjusted": ji_adjusted, "desc": ji_desc, "dongNote": dong_note,
        },
        "relationMatrix": relation_matrix,   # M9 体用互变四卦关系矩阵
        "yingqi": yingqi,                    # M2 应期推断
        "numType": num_type,                 # M6 先天/后天卦数（应期取数用）
        "analysis": analysis,
    }


# ============================ 体用旺衰（M1） ============================
_WANG_SCORE = {"旺": 2, "相": 1, "休": 0, "囚": -1, "死": -2}


def _wangshuai_view(name: str, wuxing: str, month_zhi: str, day_wx: str) -> dict:
    """八卦（体/用）的旺衰视图：月令旺相休囚死 + 日辰生克 + 综合气势。"""
    yue = wang_shuai_of(wuxing, month_zhi)
    # 日辰对卦五行的作用：日生卦=得助、日克卦=受制、卦生日=泄气、同属=比助
    if SHENG.get(day_wx) == wuxing:
        day_rel, day_score = "日辰生之（得助）", 1
    elif KE.get(day_wx) == wuxing:
        day_rel, day_score = "日辰克之（受制）", -1
    elif SHENG.get(wuxing) == day_wx:
        day_rel, day_score = "生助日辰（泄气）", -1
    elif wuxing == day_wx:
        day_rel, day_score = "与日辰同气（比助）", 1
    else:
        day_rel, day_score = "日辰无显著作用", 0

    total = _WANG_SCORE.get(yue, 0) + day_score
    if total >= 2:
        strength = "极旺"
    elif total == 1:
        strength = "偏旺"
    elif total == 0:
        strength = "中和"
    elif total == -1:
        strength = "偏衰"
    else:
        strength = "极衰"

    note = (f"{name}（{wuxing}）值月令{month_zhi}为「{yue}」，{day_rel}；"
            f"综合气势「{strength}」")
    return {
        "name": name, "wuxing": wuxing, "monthZhi": month_zhi,
        "yueWang": yue, "dayRelation": day_rel, "strength": strength,
        "score": total, "note": note,
    }


def _adjust_ji_by_wang(relation: str, ji: str, ti_strength: str) -> tuple[str, str]:
    """按体卦旺衰修正吉凶：体衰则减吉、体旺则增吉。

    传统梅花要旨：体卦宜旺不宜衰。体衰不受生助（"用生体"也难救），
    体旺则能任受克（"用克体"亦可为）。
    """
    if ti_strength in ("极衰", "偏衰"):
        downgrade = {"吉": "小吉", "小吉": "平", "平": "小凶", "小凶": "凶", "凶": "凶"}
        return ji, downgrade.get(ji, ji)
    if ti_strength in ("极旺", "偏旺"):
        upgrade = {"凶": "小凶", "小凶": "平", "平": "小吉", "小吉": "吉", "吉": "吉"}
        return ji, upgrade.get(ji, ji)
    return ji, ji


def _shengke(ti_wx: str, yong_wx: str) -> tuple[str, str, str]:
    """体用生克：返回 (关系, 吉凶, 说明)。"""
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if sheng.get(yong_wx) == ti_wx:
        return "用生体", "吉", f"用卦{_WX_NAME[yong_wx]}生体卦{_WX_NAME[ti_wx]}，外助内吉，诸事得助"
    if yong_wx == ti_wx:
        return "比和", "吉", f"体用同属{_WX_NAME[ti_wx]}，内外同心，事易成"
    if ke.get(ti_wx) == yong_wx:
        return "体克用", "小吉", f"体卦{_WX_NAME[ti_wx]}克用卦{_WX_NAME[yong_wx]}，我制于外，事可为但费心力"
    if sheng.get(ti_wx) == yong_wx:
        return "体生用", "小凶", f"体卦{_WX_NAME[ti_wx]}生用卦{_WX_NAME[yong_wx]}，我泄于外，付出多而回报缓"
    return "用克体", "凶", f"用卦{_WX_NAME[yong_wx]}克体卦{_WX_NAME[ti_wx]}，外势压我，事多阻逆，宜守不宜攻"


_WX_NAME = {"木": "木", "火": "火", "土": "土", "金": "金", "水": "水"}

# 生克关系 → 吉凶分值（用于 M9 四卦矩阵聚合）
_JI_SCORE = {"用生体": 2, "比和": 1, "体克用": 0.5, "体生用": -1, "用克体": -2}


def _score_to_ji(score: float) -> str:
    """吉凶分值 → 标签。"""
    if score >= 2:
        return "吉"
    if score >= 0.5:
        return "小吉"
    if score == 0:
        return "平"
    if score >= -1:
        return "小凶"
    return "凶"


def _aggregate_vs_hexagram(ti_wx: str, hx: dict | None) -> tuple[str, str]:
    """体卦五行 vs 一卦（上下卦各自）的生克聚合 → (综合吉凶, 明细)。

    互卦/变卦为整卦，体用生克取其上下两卦分别与体卦论生克后综合：
    任一得生助即倾向有利，双受克泄则不利。
    """
    if not hx:
        return "", ""
    pairs = []
    for tg in (hx.get("upper"), hx.get("lower")):
        if tg and tg.get("wuxing"):
            rel, _, _ = _shengke(ti_wx, tg["wuxing"])
            pairs.append((tg["name"], rel))
    if not pairs:
        return "", ""
    score = sum(_JI_SCORE.get(rel, 0) for _, rel in pairs)
    detail = "、".join(f"{name}{rel}" for name, rel in pairs)
    return _score_to_ji(score), detail


def _relation_matrix(ti: dict, yong: dict, hu_view: dict | None,
                     bian_view: dict | None, dong: int) -> list[dict]:
    """M9：体用互变四卦关系矩阵（体↔用 / 体↔互 / 体↔变 / 用↔变）。"""
    rows: list[dict] = []
    rel, ji, _ = _shengke(ti["wuxing"], yong["wuxing"])
    rows.append({"from": "体", "to": "用", "ji": ji,
                 "detail": f"体{ti['name']}{rel}用{yong['name']}"})
    ji_h, detail_h = _aggregate_vs_hexagram(ti["wuxing"], hu_view)
    if ji_h:
        rows.append({"from": "体", "to": "互", "ji": ji_h, "detail": detail_h})
    ji_b, detail_b = _aggregate_vs_hexagram(ti["wuxing"], bian_view)
    if ji_b:
        rows.append({"from": "体", "to": "变", "ji": ji_b, "detail": detail_b})
    ji_yb, detail_yb = _aggregate_vs_hexagram(yong["wuxing"], bian_view)
    if ji_yb:
        rows.append({"from": "用", "to": "变", "ji": ji_yb, "detail": detail_yb})
    return rows


# 五行 → 当令月支（梅花应期"月令定时令"用）
_WX_LING_MONTH = {"木": "寅、卯", "火": "巳、午", "土": "辰、戌、丑、未",
                  "金": "申、酉", "水": "亥、子"}


def _yingqi_meihua(shang_gua: str, xia_gua: str, dong: int, ti: dict, yong: dict,
                   hu_view: dict | None, bian_view: dict | None,
                   ti_wang: dict, yong_wang: dict, month_zhi: str, day_gan: str,
                   day_zhi: str, num_type: str = "xian") -> dict:
    """M2：梅花应期推断。

    梅花应期要诀"数取先天，卦定后天"：以卦先天数（或后天数）相加定数，
    体用旺衰定迟速，体卦五行当令月定时令，互变卦参断加速/迟滞。
    返回 {summary, points}，points 为分项提示。
    """
    ti_wx = ti["wuxing"]
    ti_strength = ti_wang.get("strength", "中和")
    yong_wx = yong["wuxing"]
    yong_strength = yong_wang.get("strength", "中和")
    num_label = "先天数" if num_type != "hou" else "后天数（洛书）"

    if ti_strength in ("极旺", "偏旺"):
        speed, unit = "应期近，多在三五日乃至月内可成", "日"
    elif ti_strength in ("极衰", "偏衰"):
        speed, unit = "应期远，须待体卦转出旺相，或数月乃至岁后方可成", "月"
    else:
        speed, unit = "应期中等，待生旺之期而动", "旬"

    s_num = trigram_num(shang_gua, num_type)
    x_num = trigram_num(xia_gua, num_type)
    total = s_num + x_num + dong

    ling = _WX_LING_MONTH.get(ti_wx, "")

    points: list[dict] = []
    points.append({"label": "旺衰定迟速",
                   "text": f"体卦{ti['name']}（{ti_wx}）气势「{ti_strength}」：{speed}。"
                            f"（用卦{yong['name']}（{yong_wx}）气势「{yong_strength}」，"
                            f"{'用旺助成' if yong_strength in ('极旺', '偏旺') else '用衰减力'}）"})
    points.append({"label": "卦数之期",
                   "text": f"{num_label}：上卦{shang_gua}({s_num}) + 下卦{xia_gua}({x_num}) "
                            f"+ 动爻{dong} = {total}，应期约 {total}{unit}（体旺则速、体衰则迟）。"})
    points.append({"label": "月令之时",
                   "text": f"体卦{ti_wx}行当令之月为「{ling}」，事多应在其当旺之月或生旺之日。"})
    if bian_view:
        bji, bdetail = _aggregate_vs_hexagram(ti_wx, bian_view)
        points.append({"label": "变卦参断",
                       "text": f"变卦对体：{bdetail}（{bji}）。变卦生体则应期加速、克体则迟滞。"})
    if hu_view:
        hji, hdetail = _aggregate_vs_hexagram(ti_wx, hu_view)
        points.append({"label": "互卦参断",
                       "text": f"互卦对体：{hdetail}（{hji}）。互卦为中间过程，参其助力与否。"})
    # 旬空应期（体/用五行落空亡则事虚，应期在出空）
    xk1, xk2 = xunkong_of(day_gan, day_zhi)
    ti_empty = ti_wx in (ZHI_WUXING.get(xk1, ""), ZHI_WUXING.get(xk2, ""))
    yong_empty = yong_wx in (ZHI_WUXING.get(xk1, ""), ZHI_WUXING.get(xk2, ""))
    if ti_empty or yong_empty:
        who = "体卦" if ti_empty else "用卦"
        points.append({"label": "旬空应期",
                       "text": f"{who}落空亡（旬空{xk1}{xk2}），事体虚悬。应期在「出空」："
                               f"填实（逢{xk1}或{xk2}之日月）或冲空（日辰冲之）方动。"})

    summary = (f"应期推断（梅花『数取先天、卦定后天』经验法则，供参考）：体卦{ti_strength}，{speed}；"
               f"卦数 {total}{unit}；体{ti_wx}当令月 {ling}。"
               f"应期受月建、日辰、动变交参，宜结合所问细断。")
    return {"summary": summary, "points": points}


def _analysis_text(ben: dict, bian: dict | None, hu: dict | None, ti: dict, yong: dict,
                   relation: str, dong: int, question: str,
                   ti_wang: dict | None = None, yong_wang: dict | None = None,
                   ji: str = "", ji_raw: str = "", ji_adjusted: bool = False,
                   dong_yao_title: str = "", dong_yao_ci: str = "",
                   yingqi: dict | None = None) -> list[dict]:
    """梅花断语：本卦 / 体用 / 旺衰 / 动爻爻辞 / 互变与建议 / 应期推断。"""
    q = (question or "").strip() or "所问之事"
    p1 = (
        f"本卦「{ben['name']}」（{ben['desc']}）：上卦{ti['symbol']}{ti['name']}（{ti['meaning']}，"
        f"{ti['wuxing']}），下卦{yong['symbol']}{yong['name']}（{yong['meaning']}，{yong['wuxing']}）。"
        f"动爻在第{dong}爻，{q}已处于变化关口。"
    )
    p2 = (
        f"体用分析：体卦为{ti['symbol']}{ti['name']}（{ti['wuxing']}，代表自己），"
        f"用卦为{yong['symbol']}{yong['name']}（{yong['wuxing']}，代表环境与对方）。"
        f"体用关系为「{relation}」——{_shengke(ti['wuxing'], yong['wuxing'])[2]}。"
    )

    # M1：体用旺衰段
    p_wang = ""
    if ti_wang and yong_wang:
        verdict = ""
        if ji_adjusted:
            verdict = (f"因体卦{ti_wang['strength']}，吉凶由「{ji_raw}」修正为「{ji}」——"
                       f"{'体衰不受生助，纵吉亦减' if ti_wang['strength'] in ('极衰', '偏衰') else '体旺能任受克，纵凶亦减'}。")
        else:
            verdict = f"体卦气势{ti_wang['strength']}，吉凶维持「{ji}」不变。"
        p_wang = (
            f"体用旺衰：{ti_wang['note']}；{yong_wang['note']}。"
            f"梅花以体卦宜旺不宜衰为要——{verdict}"
        )

    # M4：动爻爻辞段
    p_yaoci = ""
    if dong_yao_ci:
        p_yaoci = f"动爻爻辞：本卦{ben['name']}第{dong}爻（{dong_yao_title}）曰「{dong_yao_ci}」——动爻为事之枢纽，此爻之辞可作断事之印证。"

    p3_parts = []
    if hu:
        hu_up, hu_lo = _gua_view(hu["upper"]), _gua_view(hu["lower"])
        p3_parts.append(f"互卦「{hu['name']}」（{hu['desc']}）示中间过程：{hu_up['name']}{hu_up['symbol']}"
                       f"+{hu_lo['name']}{hu_lo['symbol']}，宜{hu_up['virtue']}与{hu_lo['virtue']}兼顾。")
    if bian:
        b_up, b_lo = _gua_view(bian["upper"]), _gua_view(bian["lower"])
        p3_parts.append(f"变卦「{bian['name']}」（{bian['desc']}）示最终走向："
                        f"动后变出{b_up['name']}{b_lo['name']}，结局渐明朗。")
    advice = ('主动推进、把握时机' if relation in ('用生体', '比和')
              else '稳中求进、不宜冒进' if relation == '体克用'
              else '先蓄力再行动、避免强求' if relation == '体生用'
              else '暂避锋芒、谋定后动')
    # 体衰时建议更趋保守
    if ti_wang and ti_wang["strength"] in ("极衰", "偏衰"):
        advice += "（体卦偏衰，更宜蓄力固本、不宜强求）"
    p3_parts.append(f"AI 建议：{q}宜{advice}。应期可参考体用旺衰与变卦应爻之期。")

    out = [{"title": "本卦起象", "text": p1}, {"title": "体用生克", "text": p2}]
    if p_wang:
        out.append({"title": "体用旺衰", "text": p_wang})
    if p_yaoci:
        out.append({"title": "动爻爻辞", "text": p_yaoci})
    out.append({"title": "互变与建议", "text": "".join(p3_parts)})
    # M2：应期推断段
    if yingqi:
        yingqi_text = yingqi.get("summary", "")
        out.append({"title": "应期推断", "text": yingqi_text})
    return out
