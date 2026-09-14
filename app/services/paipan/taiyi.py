# -*- coding: utf-8 -*-
"""太乙神数排局服务 —— 三式之一（奇门遁甲 / 大六壬 / 太乙神数）。

⚠️ 流派声明（务必先读）
----------------------
太乙神数是三式中**流派分歧最大**的一式：积年基准、文昌起例、主客算法在不同典籍
（《太乙金镜式经》《太乙统宗宝鉴》《太乙数统宗》等）中互不相同，至今没有公认标准。
本模块不冒充"唯一正统"，而是实现一套**自洽、可复现、每步都写明所采之说**的
「太乙年计简化模型」，并把不确定的部分显式标注出来。

确定部分（可放心使用）
----------------------
1. **太乙积年**：`JITIAN_BASE + (公元年 − 基准年)`，基准可调（见 JINIAN_BASE / JINIAN_BASE_YEAR）。
2. **太乙行宫**：太乙行八卦（乾离艮震兑坤坎巽），**不入中五**，三年一徙宫，
   二十四年一小周、七十二年一大周。
3. **阴阳遁**：太乙居阳卦宫（乾/坎/艮/震）为阳遁，居阴卦宫（离/坤/兑/巽）为阴遁。
4. **十六宫神**：子地主、丑阳德、艮和德、寅吕申、卯高丛、辰太阳、巽大灵、巳大神、
   午大威、未天道、坤大武、申武德、酉太簇、戌阴主、乾阴德、亥大义 —— 固定配宫，各本一致。

所采之说（流派差异大，已在输出 `provenance` 字段标注）
---------------------------------------------------
- 文昌（主目）：自「武德（申）」起，按积年行十六宫（阳遁顺、阴遁逆）。
- 始击（客目）：自「地主（子）」起，按积年行十六宫（方向与文昌相反）。
- 计神：自「和德（艮）」起，按积年行十二支；合神：文昌位之六合位。
- 主算 / 客算：自文昌（始击）沿行宫方向数至太乙前一宫，所得宫数（1~16）。
- 主客大将 / 参将：由主客算落宫推得（九宫循环，中五寄坤二）。

结论仅供娱乐与传统文化参考，不构成任何决策依据。
"""

from __future__ import annotations

from lunar_python import Solar

from .yijing_data import ZHI

# ===== 积年基准 =====
# 太乙上元甲子积年基数（对应公元 1984 甲子年）。不同典籍基数不同，此处取流传较广的一种。
JINIAN_BASE = 10153917
JINIAN_BASE_YEAR = 1984

# ===== 十六宫（顺时针自子起）=====
# 十二地支 + 四维（乾、坤、艮、巽），共十六位
RING_16 = ["子", "丑", "艮", "寅", "卯", "辰", "巽", "巳",
           "午", "未", "坤", "申", "酉", "戌", "乾", "亥"]

# 十六宫固定神名（各本一致）
SHEN_16 = {
    "子": "地主", "丑": "阳德", "艮": "和德", "寅": "吕申",
    "卯": "高丛", "辰": "太阳", "巽": "大灵", "巳": "大神",
    "午": "大威", "未": "天道", "坤": "大武", "申": "武德",
    "酉": "太簇", "戌": "阴主", "乾": "阴德", "亥": "大义",
}

SHEN_16_DESC = {
    "地主": "万物始生，主静守根本",
    "阳德": "阳气渐长，主施惠布德",
    "和德": "阴阳和合，主调停和解",
    "吕申": "阳气伸舒，主伸展通达",
    "高丛": "草木丛生，主积聚成势",
    "太阳": "光明普照，主显达昭著",
    "大灵": "神灵感应，主灵感启悟",
    "大神": "神威赫赫，主威权显耀",
    "大威": "威烈炽盛，主刚猛有威",
    "天道": "天理流行，主持正守中",
    "大武": "武备刚强，主征伐决断",
    "武德": "以武辅德，主文武相济",
    "太簇": "阳气簇聚，主聚敛收藏",
    "阴主": "阴气主事，主内敛潜藏",
    "阴德": "阴柔布德，主暗中得助",
    "大义": "义理昭然，主公正取裁",
}

# ===== 九宫八卦（太乙行宫用，不入中五）=====
# 宫数 → (卦名, 方位, 十六宫位, 阴阳)
GONG_9 = {
    1: ("乾", "西北", "乾", "阳"),
    2: ("离", "正南", "午", "阳"),   # 离为阴卦，但太乙局中离宫属"阴遁" — 见 YIN_GONG
    3: ("艮", "东北", "艮", "阳"),
    4: ("震", "正东", "卯", "阳"),
    6: ("兑", "正西", "酉", "阴"),
    7: ("坤", "西南", "坤", "阴"),
    8: ("坎", "正北", "子", "阴"),   # 坎为阳卦，但太乙局中坎宫属"阴遁"
    9: ("巽", "东南", "巽", "阴"),
}

# 太乙行宫顺序（按宫数，跳过中五）
TAIYI_SEQ = [1, 2, 3, 4, 6, 7, 8, 9]

# 阳遁 / 阴遁：太乙居此宫为阳遁
YANG_GONG = {1, 3, 4, 8}   # 乾、艮、震、坎 —— 阳卦方位
YIN_GONG = {2, 6, 7, 9}    # 离、兑、坤、巽 —— 阴卦方位

# 六合（合神用）
LIU_HE_16 = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
             "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午",
             "艮": "坤", "坤": "艮", "乾": "巽", "巽": "乾"}

# 十二支（计神行支用）
ZHI_12 = list(ZHI)


def _ring_idx(pos: str) -> int:
    return RING_16.index(pos)


def _ring_at(i: int) -> str:
    return RING_16[i % 16]


def _gong_by_pos(pos: str) -> int | None:
    for num, (_gua, _dir, p, _yy) in GONG_9.items():
        if p == pos:
            return num
    return None


def compute_taiyi(year: int, month: int = 1, day: int = 1, hour: int | None = None,
                  gender: str = "男", time_text: str = "", question: str = "") -> dict:
    """太乙神数年计排局，返回与前端 TaiyiModule 对齐的 dict。"""
    h = hour if hour is not None else 12

    solar = Solar.fromYmdHms(year, month, day, h, 0, 0)
    lunar = solar.getLunar()
    nian_ganzhi = lunar.getYearInGanZhi()

    # ---- 1. 太乙积年与局序 ----
    ji_nian = JINIAN_BASE + (year - JINIAN_BASE_YEAR)
    ju = (ji_nian % 72) + 1                 # 七十二局序（1~72）
    xiao_zhou = (ji_nian % 24) + 1          # 二十四小周序（1~24）

    # ---- 2. 太乙行宫（三年一徙，不入中五）----
    gong_idx = (ji_nian // 3) % 8
    tai_yi_gong = TAIYI_SEQ[gong_idx]
    gua, fang, tai_yi_pos, _ = GONG_9[tai_yi_gong]
    yang_dun = tai_yi_gong in YANG_GONG
    dun = "阳遁" if yang_dun else "阴遁"

    # ---- 3. 文昌（主目）/ 始击（客目）：自固定起点按积年行十六宫 ----
    step = ji_nian % 16
    if yang_dun:
        wen_chang = _ring_at(_ring_idx("申") + step)     # 武德（申）起，顺行
        shi_ji = _ring_at(_ring_idx("子") - step)        # 地主（子）起，逆行
    else:
        wen_chang = _ring_at(_ring_idx("申") - step)     # 阴遁逆行
        shi_ji = _ring_at(_ring_idx("子") + step)

    # ---- 4. 计神（行十二支）/ 合神（文昌之六合）----
    ji_shen = ZHI_12[(_ring_idx("艮") + (ji_nian % 12)) % 12] if yang_dun \
        else ZHI_12[(_ring_idx("艮") - (ji_nian % 12)) % 12]
    he_shen = LIU_HE_16.get(wen_chang, wen_chang)

    # ---- 5. 主算 / 客算：自文昌（始击）沿行宫方向数至太乙前一宫 ----
    ty_idx = _ring_idx(tai_yi_pos)
    # 太乙前一宫：行宫序中前一位（对应洛书宫数的前一个）
    prev_gong = TAIYI_SEQ[(gong_idx - 1) % 8]
    prev_pos = GONG_9[prev_gong][2]
    target_idx = _ring_idx(prev_pos)
    direction = 1 if yang_dun else -1

    def _suan(start_pos: str) -> int:
        """自 start_pos 起，沿行宫方向数至太乙前一宫（含首尾），返回宫数 1~16。"""
        s = _ring_idx(start_pos)
        for k in range(1, 17):
            if _ring_at(s + direction * (k - 1)) == _ring_at(target_idx):
                return k
        return 16

    zhu_suan = _suan(wen_chang)
    ke_suan = _suan(shi_ji)

    # ---- 6. 主客大将 / 参将：由主客算落宫 ----
    def _da_jiang(suan: int) -> int:
        g = ((suan - 1) % 9) + 1
        return 2 if g == 5 else g      # 中五不居，寄坤二

    def _can_jiang(dajiang_gong: int) -> int:
        g = ((dajiang_gong * 3 - 1) % 9) + 1
        return 2 if g == 5 else g      # 三因之，满九去之

    zhu_da = _da_jiang(zhu_suan)
    ke_da = _da_jiang(ke_suan)
    zhu_can = _can_jiang(zhu_da)
    ke_can = _can_jiang(ke_da)

    def _gong_item(num: int) -> dict:
        g, f, p, _ = GONG_9[num]
        return {"gong": num, "gua": g, "fang": f, "pos": p, "shen": SHEN_16.get(p, "")}

    # ---- 7. 十六宫神位（固定配宫 + 本局落神）----
    luo = {
        "太乙": tai_yi_pos,
        "文昌": wen_chang,
        "始击": shi_ji,
        "计神": ji_shen,
        "合神": he_shen,
        "主大将": GONG_9[zhu_da][2],
        "客大将": GONG_9[ke_da][2],
        "主参将": GONG_9[zhu_can][2],
        "客参将": GONG_9[ke_can][2],
    }
    shi_liu_gong = []
    for pos in RING_16:
        stars = [name for name, p in luo.items() if p == pos]
        shi_liu_gong.append({
            "pos": pos,
            "shen": SHEN_16[pos],
            "desc": SHEN_16_DESC[SHEN_16[pos]],
            "stars": stars,
            "isTaiYi": pos == tai_yi_pos,
        })

    # ---- 8. 断语 ----
    if zhu_suan > ke_suan:
        verdict = "主算胜客算，我强彼弱，宜主动进取。"
    elif zhu_suan < ke_suan:
        verdict = "客算胜主算，彼强我弱，宜守静待时。"
    else:
        verdict = "主客算等，势均力敌，宜和不宜争。"

    if yang_dun:
        dun_desc = "阳遁：阳气用事，利于外动、开创、进取。"
    else:
        dun_desc = "阴遁：阴气用事，利于内守、收敛、蓄势。"

    analysis = (
        f"{year}年（{nian_ganzhi}）太乙积年 {ji_nian}，"
        f"局序第七十二局之第 {ju} 局，小周第 {xiao_zhou} 年。"
        f"太乙居{tai_yi_gong}宫{gua}（{fang}·{tai_yi_pos}位），{dun}。"
        f"文昌在{wen_chang}（{SHEN_16[wen_chang]}），始击在{shi_ji}（{SHEN_16[shi_ji]}）；"
        f"主算 {zhu_suan}、客算 {ke_suan}。{dun_desc}{verdict}"
    )

    guide = [
        {"icon": "☯️", "title": "太乙居宫", "note": f"第 {tai_yi_gong} 宫 · {gua} · {fang} · {dun}",
         "color": "#d4a853"},
        {"icon": "📜", "title": "文昌（主目）", "note": f"{wen_chang}位 · {SHEN_16[wen_chang]} · {SHEN_16_DESC[SHEN_16[wen_chang]]}",
         "color": "#b8a6ff"},
        {"icon": "⚔️", "title": "始击（客目）", "note": f"{shi_ji}位 · {SHEN_16[shi_ji]} · {SHEN_16_DESC[SHEN_16[shi_ji]]}",
         "color": "#ff8e53"},
        {"icon": "🔢", "title": "主客算", "note": f"主算 {zhu_suan} / 客算 {ke_suan} —— {verdict}",
         "color": "#5ce1e6"},
        {"icon": "🎖️", "title": "主客将",
         "note": f"主大将 {zhu_da}宫 / 主参将 {zhu_can}宫；客大将 {ke_da}宫 / 客参将 {ke_can}宫",
         "color": "#4ade80"},
    ]

    return {
        # BasePaipanResponse 必填三件套（与 qimen / ziwei 同口径）
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "timeText": time_text or ("不详" if hour is None else f"{h}时"),
        "type": "太乙神数",
        "jiNian": ji_nian,
        "ju": ju,
        "xiaoZhou": xiao_zhou,
        "ganZhi": nian_ganzhi,
        "taiYiGong": _gong_item(tai_yi_gong),
        "dun": dun,
        "yangDun": yang_dun,
        "wenChang": {"pos": wen_chang, "shen": SHEN_16[wen_chang],
                     "desc": SHEN_16_DESC[SHEN_16[wen_chang]]},
        "shiJi": {"pos": shi_ji, "shen": SHEN_16[shi_ji],
                  "desc": SHEN_16_DESC[SHEN_16[shi_ji]]},
        "jiShen": {"pos": ji_shen, "shen": SHEN_16.get(ji_shen, "")},
        "heShen": {"pos": he_shen, "shen": SHEN_16.get(he_shen, "")},
        "zhuSuan": zhu_suan,
        "keSuan": ke_suan,
        "zhuDaJiang": _gong_item(zhu_da),
        "keDaJiang": _gong_item(ke_da),
        "zhuCanJiang": _gong_item(zhu_can),
        "keCanJiang": _gong_item(ke_can),
        "shiLiuGong": shi_liu_gong,
        "verdict": verdict,
        "dunDesc": dun_desc,
        "analysis": analysis,
        "guide": guide,
        "question": question,
        # 明确标注本模块的确定性边界，前端应据此后撤权威性措辞
        "provenance": (
            "太乙流派分歧极大：积年基准、文昌起例、主客算法各本不同。"
            "本局采用「通用年计简化模型」（行宫/阴阳遁/十六宫神为确定部分；"
            "文昌、始击、计神、合神、主客算、主客将属所采之说），仅供娱乐与传统文化参考。"
        ),
    }
