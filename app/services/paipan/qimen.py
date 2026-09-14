# -*- coding: utf-8 -*-
"""奇门遁甲排盘服务 —— 时家奇门 · 拆补法定局。

算法：
1. 定局：取输入时刻最近的已过节气（lunar-python 节气表），查节气上/中/下元局数表；
   日干支 60 甲子序求旬首（符头），旬首支 子午卯酉=上元、寅申巳亥=中元、辰戌丑未=下元；
   冬至→芒种为阳遁（顺布），夏至→大雪为阴遁（逆布）。
2. 地盘三奇六仪：戊己庚辛壬癸丁丙乙，阳遁从局数宫顺布，阴遁逆布（洛书九宫）。
3. 值符/值使：时柱所在旬的旬首奇仪（戊己庚辛壬癸）之地盘宫 = 值符宫，
   该宫原始九星 = 值符星、原始八门 = 值使门；值符星随时干转至时干地盘宫。
4. 天盘九星、八门、八神按阳顺/阴逆飞布。

输出与前端 bugua 页 QimenModule 数据结构对齐：
type / valueFu / valueShi / shiGan / palaces / qi / guide。
"""

from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

# ===== 洛书九宫 =====
# 宫序 1-9：坎一、坤二、震三、巽四、中五、乾六、兑七、艮八、离九
GONG_DIR = {
    1: "坎一宫 · 正北", 2: "坤二宫 · 西南", 3: "震三宫 · 正东", 4: "巽四宫 · 东南",
    5: "中五宫", 6: "乾六宫 · 西北", 7: "兑七宫 · 正西", 8: "艮八宫 · 东北", 9: "离九宫 · 正南",
}
GONG_DIR_SHORT = {1: "正北", 2: "西南", 3: "正东", 4: "东南", 5: "中五", 6: "西北", 7: "正西", 8: "东北", 9: "正南"}

# 九星原始宫位 / 八门原始宫位
PALACE_STAR = {1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽", 6: "天心", 7: "天柱", 8: "天任", 9: "天英"}
PALACE_DOOR = {1: "休门", 2: "死门", 3: "伤门", 4: "杜门", 6: "开门", 7: "惊门", 8: "生门", 9: "景门"}  # 中五无门

STAR_GONG = {v: k for k, v in PALACE_STAR.items()}
DOOR_GONG = {v: k for k, v in PALACE_DOOR.items()}

# 星序（按洛书宫位）：蓬 芮 冲 辅 禽 心 柱 任 英
STAR_SEQ = ["天蓬", "天芮", "天冲", "天辅", "天禽", "天心", "天柱", "天任", "天英"]
# 门序（除中五）：休 死 伤 杜 开 惊 生 景（宫位 1,2,3,4,6,7,8,9）
DOOR_SEQ = ["休门", "死门", "伤门", "杜门", "开门", "惊门", "生门", "景门"]
DOOR_GONG_SEQ = [1, 2, 3, 4, 6, 7, 8, 9]

# 八神（阳遁顺布、阴遁逆布，跳过中五）
GOD_SEQ = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]

# 三奇六仪（地盘奇仪顺序）
QIYI_SEQ = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]

# 节气局数表（上元, 中元, 下元）—— 拆补法标准表
YANG_JU = {  # 冬至 → 芒种（阳遁）
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
}
YIN_JU = {  # 夏至 → 大雪（阴遁）
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 1, 7),
}

GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 旬首（甲子/甲戌/甲申/甲午/甲辰/甲寅）对应的三奇六仪
XUNSHOU_QIYI = {0: "戊", 10: "己", 20: "庚", 30: "辛", 40: "壬", 50: "癸"}

# 星/门/神吉凶
STAR_JIXIONG = {"天心": "吉", "天任": "吉", "天辅": "吉", "天禽": "吉", "天冲": "平", "天英": "凶", "天芮": "凶", "天柱": "凶", "天蓬": "凶"}
DOOR_JIXIONG = {"开门": "吉", "休门": "吉", "生门": "吉", "杜门": "平", "景门": "平", "死门": "凶", "惊门": "凶", "伤门": "凶"}

# 神煞色（前端渲染用）
STAR_COLOR = {"天蓬": "#ff6b6b", "天芮": "#5ce1e6", "天冲": "#ff6b6b", "天辅": "#f0a6ca",
              "天禽": "#d4a853", "天心": "#b8a6ff", "天柱": "#5ce1e6", "天任": "#ff8e53", "天英": "#ff6b6b"}
DOOR_COLOR = {"休门": "#ff6b6b", "生门": "#4ade80", "伤门": "#5ce1e6", "杜门": "#5ce1e6",
              "景门": "#d4a853", "死门": "#ff6b6b", "惊门": "#d4a853", "开门": "#d4a853"}


def _time_to_hour(time_text: str) -> int:
    mapping = {
        "子时": 0, "丑时": 2, "寅时": 4, "卯时": 6, "辰时": 8, "巳时": 10,
        "午时": 12, "未时": 14, "申时": 16, "酉时": 18, "戌时": 20, "亥时": 22,
    }
    for k, v in mapping.items():
        if time_text.startswith(k):
            return v
    return 12


def _ganzhi_index(gan: str, zhi: str) -> int:
    """六十甲子索引（甲子=0 … 癸亥=59）。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for k in range(6):
        if (gi + 10 * k) % 12 == zi:
            return gi + 10 * k
    return 0


# getJieQiTable 同时返回拼音键（如 DONG_ZHI）与中文键（如 冬至），
# 且二者指向不同年份的同一节气。定局须按"最近已过节气"的阳历日期判定，
# 故统一归一化为中文名后再比日期，避免取到陈旧/未来年份的节气导致定局错乱。
PINYIN_TO_CN = {
    "DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒", "LI_CHUN": "立春",
    "YU_SHUI": "雨水", "JING_ZHE": "惊蛰", "CHUN_FEN": "春分", "QING_MING": "清明",
    "GU_YU": "谷雨", "LI_XIA": "立夏", "XIAO_MAN": "小满", "MANG_ZHONG": "芒种",
    "XIA_ZHI": "夏至", "XIAO_SHU": "小暑", "DA_SHU": "大暑", "LI_QIU": "立秋",
    "CHU_SHU": "处暑", "BAI_LU": "白露", "QIU_FEN": "秋分", "HAN_LU": "寒露",
    "SHUANG_JIANG": "霜降", "LI_DONG": "立冬", "XIAO_XUE": "小雪", "DA_XUE": "大雪",
}


def _prev_jieqi(year: int, month: int, day: int, hour: int) -> tuple[str, str]:
    """取输入时刻最近的已过节气：返回 (节气名, 阴阳遁标记)。

    以节气阳历日期为准取"最近已过"者；拼音键与中文键归一化后取同一节气名下
    日期最大（即最近）的一个，杜绝因键名不同取到陈旧/未来节气导致定局错乱。
    """
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    table = solar.getLunar().getJieQiTable()
    now_val = year * 10000 + month * 100 + day
    best_name, best_val = None, -1
    for name, sol in table.items():
        cn = PINYIN_TO_CN.get(name, name)  # 拼音键归一化为中文
        if cn not in YANG_JU and cn not in YIN_JU:
            continue
        v = sol.getYear() * 10000 + sol.getMonth() * 100 + sol.getDay()
        if v <= now_val and v > best_val:
            best_name, best_val = cn, v
    if best_name is None:
        # 表内无节气（极少跨年情形）→ 按公历近似（立春 2/4）
        best_name = "立春" if (month, day) >= (2, 4) else "大寒"
    return best_name, "阳" if best_name in YANG_JU else "阴"


def _dingyuan(xunshou_zhi: str) -> int:
    """符头定元：子午卯酉=上元(0)，寅申巳亥=中元(1)，辰戌丑未=下元(2)。"""
    if xunshou_zhi in ("子", "午", "卯", "酉"):
        return 0
    if xunshou_zhi in ("寅", "申", "巳", "亥"):
        return 1
    return 2


def _fei_gong(start: int, steps: int, shun: bool) -> int:
    """从 start 宫走 steps 步（阳遁顺飞 / 阴遁逆飞），洛书 1-9 循环。"""
    seq = [1, 2, 3, 4, 5, 6, 7, 8, 9] if shun else [1, 9, 8, 7, 6, 5, 4, 3, 2]
    idx = seq.index(start)
    return seq[(idx + steps) % 9]


def _fei_seq(shun: bool) -> list[int]:
    """顺/逆飞宫序（从 1 开始）。"""
    return [1, 2, 3, 4, 5, 6, 7, 8, 9] if shun else [1, 9, 8, 7, 6, 5, 4, 3, 2]


def compute_qimen(year: int, month: int, day: int, hour: int | None = None,
                  gender: str = "男", time_text: str = "", question: str = "",
                  manual_ju: tuple | None = None) -> dict:
    """奇门遁甲排盘（时家奇门·拆补法）。

    manual_ju: 可选手动定局，格式 (yinyang: '阳'|'阴', ju_num: 1-9)。
        传入时跳过自动拆补法定局，直接用调用方指定的阴阳遁与局数；
        其余排盘逻辑（地盘/值符值使/九宫/断卦）完全一致。
    """
    h = hour if hour is not None else 12
    if time_text and hour is None:
        h = _time_to_hour(time_text)
    solar = Solar.fromYmdHms(year, month, day, h, 0, 0)
    lunar = solar.getLunar()

    # ---- 1. 定局 ----
    jieqi, _ = _prev_jieqi(year, month, day, h)  # 当前节气（用于展示）
    day_gz = lunar.getDayInGanZhi()
    day_idx = _ganzhi_index(day_gz[0], day_gz[1])

    if manual_ju is not None:
        # 手动定局：阴阳遁 + 局数由调用方显式指定，跳过拆补法推算
        yinyang, ju_num = manual_ju
    else:
        yy = "阳" if jieqi in YANG_JU else "阴"
        ju_table = YANG_JU if yy == "阳" else YIN_JU
        xun = day_idx - day_idx % 10
        xun_zhi = ZHI[xun % 12]
        yuan = _dingyuan(xun_zhi)
        ju_num = ju_table[jieqi][yuan]
        yinyang = yy
    shun = yinyang == "阳"

    # ---- 2. 地盘三奇六仪 ----
    # 阳遁：戊起局数宫顺布；阴遁：戊起局数宫逆布
    dipan: dict[str, int] = {}
    gong_for_qiyi: dict[str, int] = {}
    seq = _fei_seq(shun)
    start_idx = seq.index(ju_num)
    for i, qy in enumerate(QIYI_SEQ):
        g = seq[(start_idx + i) % 9]
        dipan[qy] = g
        gong_for_qiyi[qy] = g

    # ---- 3. 值符 / 值使 ----
    time_gz = lunar.getTimeInGanZhi()
    time_gan, time_zhi = time_gz[0], time_gz[1]
    time_idx = _ganzhi_index(time_gan, time_zhi)
    txun = time_idx - time_idx % 10
    xun_qiyi = XUNSHOU_QIYI[txun]          # 旬首奇仪：戊己庚辛壬癸
    zhifu_gong0 = dipan[xun_qiyi]          # 值符宫（旬首奇仪地盘宫）
    zhifu_star = PALACE_STAR[zhifu_gong0]  # 值符星
    zhishi_door = PALACE_DOOR.get(zhifu_gong0, "死门")  # 值使门（中五寄坤二=死门）

    # 时干地盘宫（值符星落宫）
    shigan_gong = gong_for_qiyi.get(time_gan, ju_num)

    # ---- 4. 天盘九星 ----
    # 星序从值符星开始，按顺/逆从时干宫起布
    zf_idx = STAR_SEQ.index(zhifu_star)
    tianpan_star: dict[int, str] = {}
    tianpan_gan: dict[int, str] = {}
    seq = _fei_seq(shun)
    s_idx = seq.index(shigan_gong)
    for i in range(9):
        g = seq[(s_idx + i) % 9]
        star = STAR_SEQ[(zf_idx + i) % 9]          # 阳顺：星序向后；阴逆：星序向前
        tianpan_star[g] = star
        # 星的天盘干 = 星原宫的地盘干
        src_gong = STAR_GONG[star]
        tianpan_gan[g] = next((q for q, gg in dipan.items() if gg == src_gong), "")

    # 天禽寄坤二：天禽本宫中五无位，恒寄坤二(宫2)；与旋转后坤二之星交换宫位，
    # 保证九星不重不漏、天禽落于正统寄宫。中五(宫5)为寄宫，显示旋转后落宫之星。
    _qin_gong = next((g for g, s in tianpan_star.items() if s == "天禽"), 2)
    if _qin_gong != 2:
        _kun_star = tianpan_star.get(2)
        _kun_gan = tianpan_gan.get(2)
        tianpan_star[2] = "天禽"
        tianpan_gan[2] = next((q for q, gg in dipan.items() if gg == 5), "")
        if _kun_star is not None:
            tianpan_star[_qin_gong] = _kun_star
            tianpan_gan[_qin_gong] = _kun_gan
    else:
        # 天禽本就在坤二，已合寄宫；仅补中五寄宫干（天禽天盘干=中五地盘奇仪）
        tianpan_gan[2] = next((q for q, gg in dipan.items() if gg == 5), "")

    # ---- 5. 值使门飞布（八门） ----
    # 步数 = 时支到「时柱旬首」支的时辰差（注意：不可误用日柱旬首 xun_zhi）
    step = (ZHI.index(time_zhi) - ZHI.index(ZHI[txun % 12])) % 12
    shishi_gong = zhifu_gong0
    for _ in range(step):
        shishi_gong = _fei_gong(shishi_gong, 1, shun)
    # 八门序列从值使门开始，按顺/逆布入八宫（跳过中五）
    doors: dict[int, str] = {}
    dd_idx = DOOR_SEQ.index(zhishi_door)
    d_seq = DOOR_GONG_SEQ if shun else list(reversed(DOOR_GONG_SEQ))
    d_start = d_seq.index(shishi_gong) if shishi_gong in d_seq else 0
    for i in range(8):
        g = d_seq[(d_start + i) % 8]
        doors[g] = DOOR_SEQ[(dd_idx + i) % 8]

    # ---- 6. 八神（值符随值符星落宫，其余顺/逆布，跳过中五） ----
    gods: dict[int, str] = {}
    g_seq = [1, 2, 3, 4, 6, 7, 8, 9] if shun else [1, 9, 8, 7, 6, 4, 3, 2]
    g_start = g_seq.index(shigan_gong) if shigan_gong in g_seq else 0
    for i, god in enumerate(GOD_SEQ):
        gods[g_seq[(g_start + i) % 8]] = god

    # ---- 7. 输出九宫 ----
    palaces = []
    for g in range(1, 10):
        if g == 5:
            # 中五宫：天禽寄坤二
            dipan_qy = next((q for q, gg in dipan.items() if gg == 5), "戊")
            palaces.append({
                "dir": GONG_DIR[g],
                "gong": g,
                "wuxing": GONG_WUXING[g],
                "star": tianpan_star.get(5, "天禽"),
                "starColor": STAR_COLOR.get(tianpan_star.get(5, "天禽"), "var(--text-muted)"),
                "door": "—",
                "doorColor": "var(--text-muted)",
                "god": "寄坤",
                "comb": f"{dipan_qy}土寄宫",
                "tianpan": "",
                "dipan": dipan_qy,
                "border": "var(--accent-gold)",
                "bg": "rgba(212,168,83,0.06)",
                "jixiong": "",
            })
            continue
        star = tianpan_star.get(g, "天禽")
        door = doors.get(g, "")
        god = gods.get(g, "")
        tp = tianpan_gan.get(g, "")
        dp = next((q for q, gg in dipan.items() if gg == g), "")
        comb = f"{tp}+{dp}" if tp and dp else (tp or dp or "—")
        # 吉凶综合（简化：门>星>神）
        jx = ""
        if door and DOOR_JIXIONG.get(door) == "吉":
            jx = "吉"
        elif door and DOOR_JIXIONG.get(door) == "凶":
            jx = "凶"
        if tp in ("乙", "丙", "丁") and jx != "凶":
            jx = "吉"  # 三奇临门加成
        palaces.append({
            "dir": GONG_DIR[g],
            "gong": g,
            "wuxing": GONG_WUXING[g],
            "star": star,
            "starColor": STAR_COLOR.get(star, "var(--text-muted)"),
            "door": door,
            "doorColor": DOOR_COLOR.get(door, "var(--text-muted)"),
            "god": god,
            "comb": comb,
            "tianpan": tp,
            "dipan": dp,
            "border": None,
            "bg": None,
            "jixiong": jx,
        })

    # ---- 8. 三奇方位 + 生门方位 ----
    qi = _qi_items(gong_for_qiyi, doors, gods, tianpan_gan)
    guide = _guide_items(doors, tianpan_gan, dipan, gods)

    # ---- 9. 断卦分析层（用神/奇格/空亡/马星/旺衰/应期）----
    month_gz = lunar.getMonthInGanZhi()
    month_zhi = month_gz[1] if month_gz else "申"
    month_wx = ZHI_WUXING.get(month_zhi, "金")
    analysis = _qimen_analysis(
        palaces, day_gz[0], day_gz[1], day_idx,
        time_gan, time_zhi, month_wx, question or "",
    )

    date_text = f"{year}年{month}月{day}日"
    return {
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "timeText": time_text or ("不详" if hour is None else f"{h}时"),
        "dateText": date_text,
        "jieqi": jieqi,
        "type": f"{yinyang}遁{ju_num}局",
        "valueFu": f"{zhifu_star}星",
        "valueShi": f"{zhishi_door}",
        "shiGan": time_gan,
        "shiGanZhi": time_gz,
        "riGanZhi": day_gz,
        "palaces": palaces,
        "qi": qi,
        "guide": guide,
        "yongShen": analysis["yongShen"],
        "patterns": analysis["patterns"],
        "kongWang": analysis["kongWang"],
        "maStar": analysis["maStar"],
        "wangShuai": analysis["wangShuai"],
        "yingqi": analysis["yingqi"],
    }


def _qi_items(gong_for_qiyi: dict, doors: dict, gods: dict, tianpan_gan: dict) -> list[dict]:
    """三奇（乙丙丁）落宫 + 生门方位。"""
    items = []
    qi_meta = [
        ("乙", "🟡 乙奇（日奇）", "var(--accent-gold)", "rgba(212,168,83,0.06)", "rgba(212,168,83,0.2)"),
        ("丙", "🔴 丙奇（月奇）", "#ff6b6b", "rgba(255,107,107,0.06)", "rgba(255,107,107,0.2)"),
        ("丁", "🟢 丁奇（星奇）", "var(--accent-green)", "rgba(74,222,128,0.06)", "rgba(74,222,128,0.2)"),
    ]
    for qy, title, color, bg, border in qi_meta:
        g = gong_for_qiyi.get(qy)
        if not g:
            continue
        door = doors.get(g, "—")
        god = gods.get(g, "")
        door_jx = DOOR_JIXIONG.get(door, "平")
        if g == 5:
            text = f"落中五宫（寄坤二），{qy}奇寄宫 → 居中权衡，宜整体布局"
        elif door_jx == "吉":
            text = f"落{GONG_DIR[g]}，临{door}+{god} → ⭐ 吉位，利求谋行事"
        elif door_jx == "凶":
            text = f"落{GONG_DIR[g]}，临{door}+{god} → 吉星被凶门压制，宜守"
        else:
            text = f"落{GONG_DIR[g]}，临{door}+{god} → 平位，动静皆宜"
        items.append({"title": title, "text": text, "color": color, "bg": bg, "border": border})

    # 生门方位
    sheng_gong = next((g for g, d in doors.items() if d == "生门"), 8)
    tp = tianpan_gan.get(sheng_gong, "")
    dp = ""
    items.append({
        "title": "🔵 生门方位",
        "text": f"{GONG_DIR_SHORT.get(sheng_gong, '')}（{GONG_DIR.get(sheng_gong, '')}）→ 求财最佳方向，{tp}落宫",
        "color": "var(--accent-cyan)",
        "bg": "rgba(92,225,230,0.06)",
        "border": "rgba(92,225,230,0.2)",
    })
    return items


def _guide_items(doors: dict, tianpan_gan: dict, dipan: dict, gods: dict) -> list[dict]:
    """行动指南：开门 / 生门 / 死门 / 休门 方位。"""
    guide = []
    mapping = [
        ("开门", "🟢", "最吉方位", "求官、办事、签约首选", "var(--accent-green)"),
        ("生门", "💰", "求财方位", "谈生意、投资有利", "var(--accent-gold)"),
        ("死门", "❌", "避开方位", "今日不宜往此方出行", "#ff6b6b"),
        ("休门", "🤝", "贵人方位", "暗中相助，留意身边人", "var(--primary-light)"),
    ]
    for door, icon, title, note, color in mapping:
        g = next((gg for gg, d in doors.items() if d == door), None)
        if g is None:
            continue
        tp = tianpan_gan.get(g, "")
        god = gods.get(g, "")
        extra = f"（{tp}+{god}）" if tp and god else ""
        guide.append({
            "icon": icon,
            "title": f"{door}：{GONG_DIR_SHORT.get(g, '')}",
            "note": f"{note} {extra}",
            "color": color,
            "dir": GONG_DIR.get(g, ""),
        })
    return guide


# ============================================================
#  断卦分析层（Q1 用神 / Q2 奇仪格局 / Q3 空亡 / Q4 马星 / Q6 旺衰生克 / Q5 应期）
# ============================================================

# 九宫五行
GONG_WUXING = {1: "水", 2: "土", 3: "木", 4: "木", 5: "土", 6: "金", 7: "金", 8: "土", 9: "火"}
# 九星五行
STAR_WUXING = {"天蓬": "水", "天芮": "土", "天冲": "木", "天辅": "木", "天禽": "土",
               "天心": "金", "天柱": "金", "天任": "土", "天英": "火"}
# 八门五行
DOOR_WUXING = {"休门": "水", "生门": "土", "伤门": "木", "杜门": "木", "开门": "金",
               "惊门": "金", "景门": "火", "死门": "土"}
# 三奇六仪五行
QIYI_WUXING = {"乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
               "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
# 天干五行（用神/日干我）
GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
              "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
# 地支五行
ZHI_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
              "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
# 地支→宫（辰寄坤二、戌亥寄乾六、丑寄艮八、未寄坤二）
ZHI_TO_GONG = {"子": 1, "丑": 8, "寅": 3, "卯": 4, "辰": 2, "巳": 4, "午": 9,
               "未": 2, "申": 7, "酉": 8, "戌": 6, "亥": 6}
# 驿马（申子辰→寅3，寅午戌→申7，巳酉丑→亥6，亥卯未→巳4）
# 注意：巳酉丑三合金局马在亥(6宫)，亥卯未三合木局马在巳(4宫)；
# 此前两组写反（巳酉丑给了4、亥卯未给了6），已修正。
MA_TABLE = {"申": 3, "子": 3, "辰": 3, "寅": 7, "午": 7, "戌": 7,
            "巳": 6, "酉": 6, "丑": 6, "亥": 4, "卯": 4, "未": 4}
# 六甲旬空（旬首 day_idx → 空亡两支配）
XUN_EMPTY = {0: ("戌", "亥"), 10: ("申", "酉"), 20: ("午", "未"),
             30: ("辰", "巳"), 40: ("寅", "卯"), 50: ("子", "丑")}
# 击刑（六仪入刑地：子卯刑、寅巳申刑、丑戌未刑）
JIXING = {"戊": 3, "己": 2, "庚": 3, "辛": 9, "壬": 4, "癸": 4}
# 三奇六仪地支对冲（反吟判定）
CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
         "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}

# 奇仪格局表：(天盘,地盘) → (名, 等级, 解说)
QIYI_PATTERN = {
    ("戊", "丙"): ("青龙返首", "吉", "戊加丙，青龙返首：谋事大利，动作有成。"),
    ("丙", "戊"): ("飞鸟跌穴", "吉", "丙加戊，飞鸟跌穴：贵人提携，事易成。"),
    ("乙", "丙"): ("奇仪顺遂", "吉", "乙加丙，奇仪顺遂：吉星相随，谋为顺利。"),
    ("丙", "乙"): ("日月并行", "平", "丙加乙，日月并行：公私谋为，皆可进取。"),
    ("庚", "丙"): ("太白入荧", "凶", "庚加丙，太白入荧：贼必来，防破财招非。"),
    ("丙", "庚"): ("荧惑入白", "凶", "丙加庚，荧惑入白：贼必退，客利主不利。"),
    ("乙", "辛"): ("青龙逃走", "凶", "乙加辛，青龙逃走：文书牵连，财物耗散。"),
    ("辛", "乙"): ("白虎猖狂", "凶", "辛加乙，白虎猖狂：主客相残，家破人亡之象。"),
    ("丁", "癸"): ("朱雀投江", "凶", "丁加癸，朱雀投江：文书口舌，音信沉溺。"),
    ("癸", "丁"): ("螣蛇夭矫", "凶", "癸加丁，螣蛇夭矫：虚惊怪异，事多缠绕。"),
    ("庚", "庚"): ("战格", "凶", "庚加庚，战格：兄弟相争，官讼刑伤。"),
    ("庚", "壬"): ("小格", "凶", "庚加壬，小格：谋望不成，出行迷失。"),
    ("庚", "癸"): ("大格", "凶", "庚加癸，大格：百事皆凶，出行道路阻。"),
    ("庚", "己"): ("刑格", "凶", "庚加己，刑格：官司受刑，囚狱之灾。"),
    ("庚", "辛"): ("白虎出走", "凶", "庚加辛，白虎出走：客兵惊散，占事主散。"),
    ("辛", "庚"): ("白虎出力", "凶", "辛加庚，白虎出力：主客相残，必见争讼。"),
    ("壬", "戊"): ("小蛇化龙", "吉", "壬加戊，小蛇化龙：更变得吉，小人变君子。"),
    ("壬", "丙"): ("水蛇入火", "凶", "壬加丙，水蛇入火：官灾缠绕，文书不利。"),
    ("戊", "癸"): ("青龙华盖", "平", "戊加癸，青龙华盖：门吉可谋，门凶多乖。"),
    ("癸", "戊"): ("天乙会合", "吉", "癸加戊，天乙会合：主婚姻喜庆，谋为皆遂。"),
    ("丁", "戊"): ("青龙转光", "吉", "丁加戊，青龙转光：官人升迁，文书得助。"),
    ("戊", "丁"): ("青龙转光", "吉", "戊加丁，青龙转光：官人升迁，常人威昌。"),
    ("乙", "己"): ("日奇入墓", "凶", "乙加己，日奇入墓：门凶事凶，得奇被掩。"),
    ("丙", "己"): ("火悖入刑", "凶", "丙加己，火悖入刑：文书不利，囚人必遭刑。"),
    ("丁", "己"): ("火入勾陈", "凶", "丁加己，火入勾陈：奸私冤讼，事因女人。"),
    ("己", "庚"): ("刑格反名", "凶", "己加庚，刑格反名：谋事进退不决，终必有凶。"),
}

# 用神分类（关键词 → [(用神名, 查找方式)]）；查找方式：door/star/god/qiyi/ri/shi/gong
YONGSHEN_CATEGORY = {
    "事业": [("开门", "door"), ("日干(我)", "ri"), ("时干(事)", "shi")],
    "官": [("开门", "door"), ("日干(我)", "ri")],
    "婚姻": [("六合", "god"), ("乙奇(女)", "qiyi"), ("庚(男)", "qiyi"), ("日干(我)", "ri")],
    "感情": [("六合", "god"), ("乙奇(女)", "qiyi"), ("庚(男)", "qiyi"), ("日干(我)", "ri")],
    "财": [("生门", "door"), ("日干(我)", "ri")],
    "求财": [("生门", "door"), ("日干(我)", "ri")],
    "病": [("天芮(病)", "star"), ("天心(医)", "star"), ("日干(我)", "ri")],
    "健康": [("天芮(病)", "star"), ("天心(医)", "star"), ("日干(我)", "ri")],
    "出行": [("休门", "door"), ("开门", "door"), ("日干(我)", "ri")],
    "失物": [("玄武", "god"), ("时干(事)", "shi")],
    "盗": [("玄武", "god"), ("时干(事)", "shi")],
    "官司": [("惊门", "door"), ("开门", "door"), ("日干(我)", "ri")],
    "诉讼": [("惊门", "door"), ("开门", "door"), ("日干(我)", "ri")],
    "考试": [("景门", "door"), ("天辅", "star"), ("日干(我)", "ri")],
    "学业": [("景门", "door"), ("天辅", "star"), ("日干(我)", "ri")],
    "胎": [("坤宫(母)", "gong"), ("天芮(胎)", "star")],
    "孕": [("坤宫(母)", "gong"), ("天芮(胎)", "star")],
}


def _shengke(from_wx: str, to_wx: str) -> tuple[str, int]:
    """from 对 to 的生克关系（from=我）。返回 (关系, 吉凶分)。"""
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if from_wx == to_wx:
        return "比和", 1
    if sheng[from_wx] == to_wx:        # 我生
        return "我生", -1
    if sheng[to_wx] == from_wx:        # 生我
        return "生我", 2
    if ke[from_wx] == to_wx:           # 我克
        return "我克", 1
    return "克我", -2                   # 克我


def _wang_state(month_wx: str, wx: str) -> str:
    """月令旺相休囚死（wx 五行在 month_wx 月令下，以月令为“我”）。

    以月令 M 为“我”、被测五行 X：
    同我→旺；我生(M生X)→相；生我(X生M)→休；我克(M克X)→死；克我(X克M)→囚。
    """
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if wx == month_wx:
        return "旺"                         # 同我 → 旺
    if sheng[month_wx] == wx:
        return "相"                         # 我生（月令生之）→ 相
    if sheng[wx] == month_wx:
        return "休"                         # 生我（生月令者）→ 休
    if ke[month_wx] == wx:
        return "死"                         # 我克（月令克之）→ 死
    return "囚"                             # 克我（克月令者）→ 囚


def _find_gong_for_gan(palaces: list[dict], gan: str) -> int | None:
    """定位某天干落宫（甲遁于戊，故甲→戊宫）。"""
    target = "戊" if gan == "甲" else gan
    for p in palaces:
        if p.get("tianpan") == target or p.get("dipan") == target:
            return p.get("gong")
    return None


def _locate(palaces: list[dict], kind: str, value: str, day_gan: str, time_gan: str) -> int | None:
    if kind == "ri":
        return _find_gong_for_gan(palaces, day_gan)
    if kind == "shi":
        return _find_gong_for_gan(palaces, time_gan)
    if kind == "gong":
        return int(value)
    for p in palaces:
        if kind == "door" and p.get("door") == value:
            return p.get("gong")
        if kind == "star" and p.get("star") == value:
            return p.get("gong")
        if kind == "god" and p.get("god") == value:
            return p.get("gong")
        if kind == "qiyi" and (p.get("tianpan") == value or p.get("dipan") == value):
            return p.get("gong")
    return None


def _yongshen(palaces: list[dict], day_gan: str, time_gan: str, question: str,
              month_wx: str) -> list[dict]:
    """Q1 用神体系：立极 + 落宫 + 与日干生克 + 旺衰吉凶。"""
    # 选用神分类
    cat = "通用"
    if question:
        for kw, items in YONGSHEN_CATEGORY.items():
            if kw in question:
                cat = kw
                sel = items
                break
        else:
            sel = None
    if cat == "通用" or "sel" not in dir():
        sel = [("日干(我)", "ri"), ("时干(事)", "shi")]
    ri_gong = _find_gong_for_gan(palaces, day_gan)
    ri_wx = GAN_WUXING.get(day_gan, GONG_WUXING.get(ri_gong or 5, "土"))
    result = []
    seen = set()
    for name, kind in sel:
        if kind in ("ri", "shi"):   # 日干/时干由下方显式插入，避免重复
            continue
        g = _locate(palaces, kind, name, day_gan, time_gan)
        if g is None or g in seen:
            continue
        seen.add(g)
        p = next((x for x in palaces if x.get("gong") == g), None)
        if not p:
            continue
        # 用神五行：优先门→星→天盘奇仪→宫
        if p.get("door") and p["door"] in DOOR_WUXING:
            wx = DOOR_WUXING[p["door"]]
            sym = p["door"]
        elif p.get("star") and p["star"] in STAR_WUXING:
            wx = STAR_WUXING[p["star"]]
            sym = p["star"]
        elif p.get("tianpan") and p["tianpan"] in QIYI_WUXING:
            wx = QIYI_WUXING[p["tianpan"]]
            sym = p["tianpan"]
        else:
            wx = GONG_WUXING.get(g, "土")
            sym = GONG_DIR[g]
        rel, score = _shengke(ri_wx, wx)
        # 门/星本吉凶
        base_jx = "平"
        if p.get("door") and DOOR_JIXIONG.get(p["door"]) == "吉":
            base_jx = "吉"
        elif p.get("door") and DOOR_JIXIONG.get(p["door"]) == "凶":
            base_jx = "凶"
        if score >= 2:
            jx = "吉"
        elif score == 1:
            jx = "小吉" if base_jx != "凶" else "平"
        elif score == -1:
            jx = "小凶" if base_jx != "吉" else "平"
        else:
            jx = "凶"
        wang = _wang_state(month_wx, wx)
        note = (f"{sym}（{wx}）与日干{day_gan}（{ri_wx}）{rel}"
                f"；月令{wang}；门/星{base_jx} → {jx}")
        result.append({
            "name": name,
            "gong": g,
            "gongName": GONG_DIR[g],
            "wuxing": wx,
            "symbol": sym,
            "star": p.get("star"),
            "door": p.get("door"),
            "god": p.get("god"),
            "tianpan": p.get("tianpan"),
            "dipan": p.get("dipan"),
            "relation": rel,
            "wang": wang,
            "jixiong": jx,
            "note": note,
        })
    # 日干本宫信息（求测人）
    if ri_gong is not None:
        rp = next((x for x in palaces if x.get("gong") == ri_gong), None)
        if rp:
            result.insert(0, {
                "name": "日干(求测人)",
                "gong": ri_gong,
                "gongName": GONG_DIR[ri_gong],
                "wuxing": ri_wx,
                "symbol": day_gan,
                "star": rp.get("star"),
                "door": rp.get("door"),
                "god": rp.get("god"),
                "tianpan": rp.get("tianpan"),
                "dipan": rp.get("dipan"),
                "relation": "我",
                "wang": _wang_state(month_wx, ri_wx),
                "jixiong": "—",
                "note": f"日干{day_gan}（{ri_wx}）落{GONG_DIR[ri_gong]}，为求测人立极点。",
            })
    # 时干（事体）本宫信息
    shi_gong = _find_gong_for_gan(palaces, time_gan)
    if shi_gong is not None and shi_gong != ri_gong:
        sp = next((x for x in palaces if x.get("gong") == shi_gong), None)
        if sp:
            result.append({
                "name": "时干(事)",
                "gong": shi_gong,
                "gongName": GONG_DIR[shi_gong],
                "wuxing": GAN_WUXING.get(time_gan, GONG_WUXING.get(shi_gong, "土")),
                "symbol": time_gan,
                "star": sp.get("star"),
                "door": sp.get("door"),
                "god": sp.get("god"),
                "tianpan": sp.get("tianpan"),
                "dipan": sp.get("dipan"),
                "relation": "事",
                "wang": _wang_state(month_wx, GAN_WUXING.get(time_gan, "土")),
                "jixiong": "—",
                "note": f"时干{time_gan}（事体）落{GONG_DIR[shi_gong]}，为所问之事。",
            })
    return {"category": cat, "riGan": day_gan, "riWuxing": ri_wx, "items": result}


def _qiyi_patterns(palaces: list[dict], month_wx: str) -> list[dict]:
    """Q2 奇仪格局 + Q7 门迫/击刑/伏吟反吟。"""
    out = []
    for p in palaces:
        g = p.get("gong")
        tp, dp = p.get("tianpan"), p.get("dipan")
        if tp and dp:
            key = (tp, dp)
            if key in QIYI_PATTERN:
                name, level, desc = QIYI_PATTERN[key]
                out.append({"gong": g, "gongName": GONG_DIR[g], "tianpan": tp,
                            "dipan": dp, "name": name, "level": level, "desc": desc})
            # 伏吟（天盘==地盘）
            if tp == dp:
                out.append({"gong": g, "gongName": GONG_DIR[g], "tianpan": tp,
                            "dipan": dp, "name": "伏吟", "level": "凶",
                            "desc": f"{tp}加{tp}伏吟：事主迟滞、内守不宜动。"})
            # 反吟（天盘地支与地盘地支对冲）
            elif tp in CHONG and CHONG.get(tp) == dp:
                out.append({"gong": g, "gongName": GONG_DIR[g], "tianpan": tp,
                            "dipan": dp, "name": "反吟", "level": "凶",
                            "desc": f"{tp}加{dp}反吟：反复不定、变动多端。"})
        # 门迫：门五行克宫五行
        door = p.get("door")
        if door and door in DOOR_WUXING and g and DOOR_WUXING[door] == GONG_WUXING.get(g):
            pass
        if door and door in DOOR_WUXING and g and _shengke(DOOR_WUXING[door], GONG_WUXING.get(g, "土"))[0] == "克我":
            out.append({"gong": g, "gongName": GONG_DIR[g], "tianpan": tp or "",
                        "dipan": dp or "", "name": "门迫", "level": "凶",
                        "desc": f"{door}（{DOOR_WUXING[door]}）克{gong_dir_short(g)}宫（{GONG_WUXING.get(g)}），门迫主阻隔耗损。"})
        # 击刑：六仪入刑地
        if dp and dp in JIXING and JIXING[dp] == g:
            out.append({"gong": g, "gongName": GONG_DIR[g], "tianpan": tp or "",
                        "dipan": dp or "", "name": "击刑", "level": "凶",
                        "desc": f"{dp}仪入{gong_dir_short(g)}宫刑地，击刑主伤残刑狱。"})
    return out


def gong_dir_short(g: int) -> str:
    return GONG_DIR_SHORT.get(g, "")


def _kongwang(day_idx: int) -> dict:
    """Q3 六甲旬空 → 空亡宫。"""
    xun = day_idx - day_idx % 10
    empty_zhi = XUN_EMPTY.get(xun, ("", ""))
    empty_gongs = [ZHI_TO_GONG[z] for z in empty_zhi if z in ZHI_TO_GONG]
    return {
        "emptyZhi": list(empty_zhi),
        "emptyGongs": empty_gongs,
        "desc": f"旬空：{'、'.join(empty_zhi)}（{'、'.join(GONG_DIR.get(x, '') for x in empty_gongs)}空）",
    }


def _ma_star(zhi: str) -> dict:
    """Q4 驿马星落宫。"""
    g = MA_TABLE.get(zhi)
    if not g:
        return {"gong": None, "gongName": "", "desc": "无驿马"}
    return {"gong": g, "gongName": GONG_DIR[g],
            "desc": f"驿马在{GONG_DIR[g]}，主动象、出行、急速、远行。"}


def _yingqi(yong: dict, kong: dict, ma: dict) -> dict:
    """Q5 应期推断：内外盘 + 空亡填实 + 马星冲动 + 值使门。"""
    points = []
    items = yong.get("items", [])
    # 用神内外盘定远近
    inner = [3, 1, 8, 4]  # 内盘：震坎艮巽
    near = far = 0
    for it in items:
        g = it.get("gong")
        if g in inner:
            near += 1
        else:
            far += 1
    if near >= far:
        points.append("用神多落内盘（坎艮震巽），事应近、在本地或旬月内。")
    else:
        points.append("用神多落外盘（离坤兑乾），事应远、在他方或经年。")
    # 空亡填实
    for eg in kong.get("emptyGongs", []):
        ez = kong.get("emptyZhi", [])
        if ez:
            points.append(f"空亡宫见用神，需待{'、'.join(ez)}填实或冲空之期方应。")
            break
    # 马星冲动
    if ma.get("gong"):
        points.append(f"驿马在{ma['gongName']}，逢冲动之期（与该宫支相冲）事速发。")
    # 值使门参断
    summary = "应期以用神落宫为主，参空亡填实与驿马冲动：近则应旬月内、远则待填实冲合。"
    if not points:
        points.append("用神得地无空亡，事机已动，近期可成。")
    return {"summary": summary, "points": points}


def _qimen_analysis(palaces: list[dict], day_gan: str, day_zhi: str, day_idx: int,
                    time_gan: str, time_zhi: str, month_wx: str, question: str) -> dict:
    """汇总断卦分析层（Q1/Q2/Q3/Q4/Q5/Q6）。"""
    yong = _yongshen(palaces, day_gan, time_gan, question, month_wx)
    patterns = _qiyi_patterns(palaces, month_wx)
    kong = _kongwang(day_idx)
    ma = _ma_star(time_zhi)
    yingqi = _yingqi(yong, kong, ma)
    wang = {
        "monthWx": month_wx,
        "desc": f"本月令五行属{month_wx}（旺相休囚死据此判定）。",
        "yong": [{"name": it["name"], "wx": it["wuxing"], "state": it["wang"]}
                 for it in yong.get("items", [])],
    }
    return {
        "yongShen": yong,
        "patterns": patterns,
        "kongWang": kong,
        "maStar": ma,
        "yingqi": yingqi,
        "wangShuai": wang,
    }
