# -*- coding: utf-8 -*-
"""大六壬排盘服务 —— 三式之一（奇门遁甲 / 大六壬 / 太乙神数）。

起课步骤（通用起例）
--------------------
1. **定月将**（太阳过宫）：按**节气**取将，非农历月 —— 雨水后亥将、春分后戌将、谷雨后酉将、
   小满后申将、夏至后未将、大暑后午将、处暑后巳将、秋分后辰将、霜降后卯将、
   小雪后寅将、冬至后丑将、大寒后子将。
2. **定占时**：以所占时辰的地支为占时。
3. **布天地盘**：地盘即十二支本位（不动）；天盘以「月将加占时」顺布十二支。
4. **起四课**：日干寄宫取「干上神」为一课；干上神之上神为二课；
   日支取「支上神」为三课；支上神之上神为四课。
5. **发三传**（九宗门）：按 贼克 → 比用 → 涉害 → 遥克 → 昴星 → 别责 → 八专 → 伏吟 → 反吟
   的次序定初传；中传 = 天盘加临初传之神，末传 = 天盘加临中传之神。
6. **布十二天将**：贵人口诀起贵人（昼贵 / 夜贵），再顺逆布腾蛇…天后。

流派差异说明
------------
三式的流派分歧很大（尤其涉害深浅、别责取用、贵人顺逆三处）。本实现取流传最广的
「通用起例」，每处有分歧的地方都在代码注释里写明所采之说，便于后续按典籍校对切换。
结论仅供娱乐与传统文化参考，不构成任何决策依据。
"""

from __future__ import annotations

from lunar_python import Solar

from .yijing_data import GAN, GAN_WUXING, ZHI, ZHI_WUXING

# ===== 基础常量 =====

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE_PAIRS = {("木", "土"), ("土", "水"), ("水", "火"), ("火", "金"), ("金", "木")}

# 十二地支阴阳（子寅辰午申戌为阳，丑卯巳未酉亥为阴）
ZHI_YANGYANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}
# 十干阴阳
GAN_YANGYANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}

# 地支六冲
LIU_CHONG = {("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")}
# 三刑（含自刑）
SAN_XING = {"寅": "巳", "巳": "申", "申": "寅", "子": "卯", "卯": "子",
            "丑": "未", "未": "戌", "戌": "丑"}
ZI_XING = {"辰", "午", "酉", "亥"}  # 自刑
# 三合局（顺行次序）
SAN_HE_SEQ = [["亥", "卯", "未"], ["寅", "午", "戌"], ["巳", "酉", "丑"], ["申", "子", "辰"]]
# 驿马（三合局首支之冲）
YI_MA = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
         "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳", "卯": "巳", "未": "巳"}
# 天干五合
GAN_HE = {"甲": "己", "乙": "庚", "丙": "辛", "丁": "壬", "戊": "癸",
          "己": "甲", "庚": "乙", "辛": "丙", "壬": "丁", "癸": "戊"}

# ===== 十二天将 =====

TIAN_JIANG = ["贵人", "腾蛇", "朱雀", "六合", "勾陈", "青龙",
              "天空", "白虎", "太常", "玄武", "太阴", "天后"]

JIANG_JIXIONG = {"贵人": "吉", "腾蛇": "凶", "朱雀": "平", "六合": "吉", "勾陈": "凶", "青龙": "吉",
                 "天空": "凶", "白虎": "凶", "太常": "吉", "玄武": "凶", "太阴": "吉", "天后": "吉"}

JIANG_DESC = {
    "贵人": "主贵人扶助、逢凶化吉，谒贵求官最宜",
    "腾蛇": "主惊疑怪异、牵缠反复，事宜速决不宜迟疑",
    "朱雀": "主口舌文书、信息是非，防言语招怨",
    "六合": "主和合喜庆、交易婚姻，宜合作谋事",
    "勾陈": "主争斗迟滞、田土勾连，事宜缓不宜急",
    "青龙": "主财禄喜庆、官爵荣身，百事皆吉",
    "天空": "主虚诈不实、文书落空，防欺瞒",
    "白虎": "主凶丧疾病、道路血光，宜守不宜进",
    "太常": "主衣食宴乐、印绶爵禄，平稳得福",
    "玄武": "主盗贼阴私、暧昧失脱，防漏财被骗",
    "太阴": "主阴私暗助、密谋可成，宜暗中行事",
    "天后": "主恩泽荫庇、女性贵人，宜依附而行",
}

# 贵人口诀（阳贵在前，阴贵在后）
# 甲戊庚牛羊 / 乙己鼠猴乡 / 丙丁猪鸡位 / 壬癸兔蛇藏 / 六辛逢马虎
GUI_REN = {
    "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("子", "申"), "己": ("子", "申"),
    "丙": ("亥", "酉"), "丁": ("亥", "酉"),
    "壬": ("卯", "巳"), "癸": ("卯", "巳"),
    "辛": ("午", "寅"),
}
# 昼夜分界：卯→申 为昼（用阳贵），酉→寅 为夜（用阴贵）
DAY_ZHI = {"卯", "辰", "巳", "午", "未", "申"}

# 贵人加临地盘支在此六位则顺布十二将，其余六位逆布（所采之说：亥子丑寅卯辰顺 / 巳午未申酉戌逆）
JIANG_SHUN_ZHI = {"亥", "子", "丑", "寅", "卯", "辰"}

# ===== 月将（太阳过宫）=====

# 节气 → (月将支, 神名)
YUE_JIANG_BY_JIEQI = {
    "雨水": ("亥", "登明"), "惊蛰": ("亥", "登明"),
    "春分": ("戌", "河魁"), "清明": ("戌", "河魁"),
    "谷雨": ("酉", "从魁"), "立夏": ("酉", "从魁"),
    "小满": ("申", "传送"), "芒种": ("申", "传送"),
    "夏至": ("未", "小吉"), "小暑": ("未", "小吉"),
    "大暑": ("午", "胜光"), "立秋": ("午", "胜光"),
    "处暑": ("巳", "太乙"), "白露": ("巳", "太乙"),
    "秋分": ("辰", "天罡"), "寒露": ("辰", "天罡"),
    "霜降": ("卯", "太冲"), "立冬": ("卯", "太冲"),
    "小雪": ("寅", "功曹"), "大雪": ("寅", "功曹"),
    "冬至": ("丑", "大吉"), "小寒": ("丑", "大吉"),
    "大寒": ("子", "神后"), "立春": ("子", "神后"),
}

YUE_JIANG_DESC = {
    "亥": "登明 · 主阴私、召请、隐匿之事",
    "戌": "河魁 · 主坟墓、争斗、聚众之事",
    "酉": "从魁 · 主阴私、妇女、钱财之事",
    "申": "传送 · 主道路、行程、信息之事",
    "未": "小吉 · 主酒食、婚姻、交易之事",
    "午": "胜光 · 主文书、光彩、官禄之事",
    "巳": "太乙 · 主惊怪、梦寐、虚诈之事",
    "辰": "天罡 · 主争斗、词讼、凶恶之事",
    "卯": "太冲 · 主门户、车船、分张之事",
    "寅": "功曹 · 主官吏、文书、树木之事",
    "丑": "大吉 · 主田宅、钱财、宴喜之事",
    "子": "神后 · 主阴私、妇女、暗昧之事",
}

# ===== 日干寄宫 =====

GAN_JI_GONG = {"甲": "寅", "乙": "辰", "丙": "巳", "丁": "未", "戊": "巳",
               "己": "未", "庚": "申", "辛": "戌", "壬": "亥", "癸": "丑"}

# 八专日（干寄宫与日支同位，四课只有两课）
BA_ZHUAN_RI = {("甲", "寅"), ("乙", "卯"), ("丁", "未"), ("己", "未"),
               ("庚", "申"), ("辛", "酉"), ("癸", "丑")}


# ===== 工具 =====

def _time_to_hour(time_text: str) -> int | None:
    """时辰文本 → 小时（区间中点）；无法识别返回 None。"""
    mapping = {"子": 0, "丑": 2, "寅": 4, "卯": 6, "辰": 8, "巳": 10,
               "午": 12, "未": 14, "申": 16, "酉": 18, "戌": 20, "亥": 22}
    if not time_text:
        return None
    for k, v in mapping.items():
        if time_text.startswith(k):
            return v
    return None


def _hour_to_zhi(hour: int) -> str:
    """小时 → 时辰地支（子时跨 23:00-01:00）。"""
    return ZHI[((hour + 1) % 24) // 2]


def _zhi_add(zhi: str, n: int) -> str:
    return ZHI[(ZHI.index(zhi) + n) % 12]


def _is_ke(a: str, b: str) -> bool:
    """a 克 b（五行）。"""
    return (GAN_WUXING.get(a) or ZHI_WUXING.get(a), GAN_WUXING.get(b) or ZHI_WUXING.get(b)) in KE_PAIRS


def _wx(x: str) -> str:
    return GAN_WUXING.get(x) or ZHI_WUXING.get(x) or ""


def _ganzhi_index(gan: str, zhi: str) -> int:
    """六十甲子索引（甲子=0 … 癸亥=59）。"""
    gi, zi = GAN.index(gan), ZHI.index(zhi)
    for k in range(6):
        if (gi + 10 * k) % 12 == zi:
            return gi + 10 * k
    return 0


def _xun_gan_table(ri_gan: str, ri_zhi: str) -> tuple[dict[str, str], list[str]]:
    """旬遁干表：返回 ({地支: 天干}, 空亡两支)。

    以日柱所属六甲旬的旬首支起，顺布十干于连续十个地支，余两支为空亡（无遁干）。
    """
    idx = _ganzhi_index(ri_gan, ri_zhi)
    xun_start = idx - (idx % 10)
    first_zhi = ZHI[xun_start % 12]
    table: dict[str, str] = {}
    for k in range(10):
        table[_zhi_add(first_zhi, k)] = GAN[k]
    kong = [z for z in ZHI if z not in table]
    return table, kong


def _liuqin(day_gan: str, other_gan: str | None) -> str:
    """以日干为准定六亲。"""
    if not other_gan:
        return "—"
    if _wx(day_gan) == _wx(other_gan):
        return "比肩"
    if SHENG.get(_wx(other_gan)) == _wx(day_gan):
        return "父母"       # 生我
    if SHENG.get(_wx(day_gan)) == _wx(other_gan):
        return "子孙"       # 我生
    if _is_ke(other_gan, day_gan):
        return "官鬼"       # 克我
    if _is_ke(day_gan, other_gan):
        return "妻财"       # 我克
    return "比肩"


def _sanhe_next(zhi: str) -> str:
    """三合局中该支的次第下一位（顺行）。"""
    for tri in SAN_HE_SEQ:
        if zhi in tri:
            return tri[(tri.index(zhi) + 1) % 3]
    return zhi


def _xing(zhi: str) -> str:
    """刑神（自刑返回自身）。"""
    return SAN_XING.get(zhi, zhi)


# ===== 三传（九宗门）=====

def _san_chuan_recur(tian: dict[str, str], chu: str) -> tuple[str, str]:
    """由初传递推中传、末传：中 = 天盘加临初传之神，末 = 天盘加临中传之神。"""
    zhong = tian[chu]
    mo = tian[zhong]
    return zhong, mo


def _shehai_depth(tian: dict[str, str], shen: str) -> int:
    """涉害深浅：上神从其地盘本位起顺行十二宫回到本位，途中所遇克贼的次数。

    所采之说：「以所克之神，从本位起，历十二位，归本位，遇克多者为涉害深」。
    遇克相同则按 孟(寅申巳亥) > 仲(子午卯酉) > 季(辰戌丑未) 定深浅（由调用方处理）。
    """
    depth = 0
    for k in range(12):
        pos = _zhi_add(shen, k)
        up = tian[pos]
        if _is_ke(up, pos) or _is_ke(pos, up):
            depth += 1
    return depth


def _shenhai_rank(zhi: str) -> int:
    """孟/仲/季 深浅序：孟=2（最深）、仲=1、季=0。"""
    if zhi in ("寅", "申", "巳", "亥"):
        return 2
    if zhi in ("子", "午", "卯", "酉"):
        return 1
    return 0


def _fa_san_chuan(
    tian: dict[str, str],
    sike: list[dict],
    ri_gan: str,
    ri_zhi: str,
    gan_shang: str,
    zhi_shang: str,
    yue_jiang: str,
    zhan_shi: str,
) -> dict:
    """发三传：按九宗门次序定初传，并递推中末传。"""
    # ---- 1. 贼克法 ----
    zei = [k for k in sike if k["relation"] == "贼"]   # 下贼上
    ke = [k for k in sike if k["relation"] == "克"]    # 上克下

    if zei or ke:
        cands = zei or ke
        method = "贼克法"
        if len(cands) > 1:
            # 比用法：取与日干阴阳相比者
            same = [k for k in cands if ZHI_YANGYANG[k["upper"]] == GAN_YANGYANG[ri_gan]]
            if len(same) == 1:
                cands = same
                method = "比用法（知一）"
            elif len(same) > 1:
                cands = same
                method = "比用法"
            if len(cands) > 1:
                # 涉害法：比用后仍多，取涉害深者
                method = "涉害法"
                cands = sorted(
                    cands,
                    key=lambda k: (-_shehai_depth(tian, k["upper"]), -_shenhai_rank(k["upper"])),
                )[:1]
        k = cands[0]
        if method == "贼克法":
            if zei:
                ke_ti = "重审课"
                desc = "下贼上，事起内生，宜再三审视而后动。"
            else:
                ke_ti = "元首课"
                desc = "上克下，事起外來，尊长发动，顺理而成。"
        elif method.startswith("比用"):
            ke_ti = "知一课"
            desc = "克贼多端而比者为一，事有两端，知其一而取之。"
        else:
            ke_ti = "涉害课"
            desc = "涉害既深，机已显露，宜决断不宜因循。"
        chu = k["upper"]
        zhong, mo = _san_chuan_recur(tian, chu)
        return {"method": method, "keTi": ke_ti, "desc": desc,
                "chu": chu, "zhong": zhong, "mo": mo, "fromKe": k["label"]}

    # ---- 2. 遥克法（蒿矢 / 弹射）----
    uppers = [k["upper"] for k in sike]
    for k in sike:
        if _is_ke(k["upper"], ri_gan):
            chu = k["upper"]
            zhong, mo = _san_chuan_recur(tian, chu)
            return {"method": "遥克法 · 蒿矢", "keTi": "蒿矢课",
                    "desc": "四课无克，神遥克日，如矢及远，力弱而中。",
                    "chu": chu, "zhong": zhong, "mo": mo, "fromKe": k["label"]}
    for k in sike:
        if _is_ke(ri_gan, k["upper"]):
            chu = k["upper"]
            zhong, mo = _san_chuan_recur(tian, chu)
            return {"method": "遥克法 · 弹射", "keTi": "弹射课",
                    "desc": "日干遥克神，如弹及远，主动而力不足。",
                    "chu": chu, "zhong": zhong, "mo": mo, "fromKe": k["label"]}

    # ---- 3. 昴星法 ----
    if len(sike) >= 4:
        if GAN_YANGYANG[ri_gan] == "阳":
            chu = tian["酉"]
            zhong, mo = zhi_shang, gan_shang
            return {"method": "昴星法 · 虎视", "keTi": "虎视格",
                    "desc": "四课全无克贼，阳日取酉上神为用，虎视眈眈，宜守静观变。",
                    "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "昴星"}
        inv = {v: k for k, v in tian.items()}
        chu = inv.get("酉", "酉")
        zhong, mo = gan_shang, zhi_shang
        return {"method": "昴星法 · 冬蛇掩目", "keTi": "冬蛇掩目格",
                "desc": "四课全无克贼，阴日取酉下神为用，蛇掩其目，事宜韬晦。",
                "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "昴星"}

    # ---- 4. 别责法（四课不全，仅三课）----
    if len(sike) == 3:
        if GAN_YANGYANG[ri_gan] == "阳":
            he_gan = GAN_HE[ri_gan]
            chu = tian[GAN_JI_GONG[he_gan]]
        else:
            chu = _sanhe_next(ri_zhi)
        zhong, mo = gan_shang, gan_shang
        return {"method": "别责法", "keTi": "别责课",
                "desc": "四课不备，无克可责，别取一神为用，事有缺欠，宜借力而行。",
                "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "别责"}

    # ---- 5. 八专法（只有两课）----
    if len(sike) == 2:
        if GAN_YANGYANG[ri_gan] == "阳":
            chu = _zhi_add(gan_shang, 2)   # 从干上神顺数三位（含本位）
        else:
            chu = _zhi_add(zhi_shang, -2)  # 从支上神逆数三位
        zhong, mo = gan_shang, gan_shang
        return {"method": "八专法", "keTi": "八专课",
                "desc": "干支同位，四课止两，阴阳不分，事宜专心一志。",
                "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "八专"}

    # ---- 兜底 ----
    chu = gan_shang
    zhong, mo = _san_chuan_recur(tian, chu)
    return {"method": "常法", "keTi": "常课", "desc": "按干上神发用。",
            "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "第一课"}


# ===== 主入口 =====

def compute_liuren(year: int, month: int, day: int, hour: int | None = None,
                   gender: str = "男", time_text: str = "", question: str = "") -> dict:
    """大六壬排盘，返回与前端 LiuRenModule 对齐的 dict。"""
    h = hour if hour is not None else 12
    if h is None or (time_text and hour is None):
        h = _time_to_hour(time_text) or 12

    solar = Solar.fromYmdHms(year, month, day, h, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    ri_gan, ri_zhi = ec.getDayGan(), ec.getDayZhi()
    ri_ganzhi = ec.getDay()
    yue_jiang_zhi_from_jq: str | None = None

    # ---- 1. 月将（按节气）----
    jieqi = ""
    try:
        from .qimen import _prev_jieqi
        jieqi = _prev_jieqi(year, month, day, h)[0]
    except Exception:
        jieqi = ""
    if jieqi in YUE_JIANG_BY_JIEQI:
        yue_jiang, yue_jiang_name = YUE_JIANG_BY_JIEQI[jieqi]
    else:
        # 节气缺失时按「月建合神」近似：寅月亥将、卯月戌将……（与节气表同序）
        yue_jian = ec.getMonthZhi()
        yue_jiang = _zhi_add(yue_jian, -3)
        yue_jiang_name = YUE_JIANG_BY_JIEQI.get(jieqi, (yue_jiang, ""))[1] or ""
    yue_jiang_zhi_from_jq = yue_jiang

    # ---- 2. 占时 ----
    zhan_shi = _hour_to_zhi(h)

    # ---- 3. 天地盘：月将加占时顺布 ----
    tian = {_zhi_add(zhan_shi, k): _zhi_add(yue_jiang, k) for k in range(12)}

    # ---- 4. 四课 ----
    ji_gong = GAN_JI_GONG[ri_gan]
    gan_shang = tian[ji_gong]              # 干上神（一课上）
    gan_shang_shang = tian[gan_shang]      # 二课上
    zhi_shang = tian[ri_zhi]               # 支上神（三课上）
    zhi_shang_shang = tian[zhi_shang]      # 四课上

    def _mk_ke(label: str, lower: str, upper: str, note: str) -> dict:
        lower_wx, upper_wx = _wx(lower), _wx(upper)
        if _is_ke(upper, lower):
            rel = "克"
        elif _is_ke(lower, upper):
            rel = "贼"
        else:
            rel = ""
        rel_text = {"克": "上克下", "贼": "下贼上", "": "无克"}[rel]
        return {
            "label": label,
            "lower": lower,
            "upper": upper,
            "lowerWuxing": lower_wx,
            "upperWuxing": upper_wx,
            "relation": rel,
            "relationText": rel_text,
            "note": note,
        }

    sike = [
        _mk_ke("第一课", ri_gan, gan_shang, f"日干{ri_gan}寄{ji_gong}宫"),
        _mk_ke("第二课", gan_shang, gan_shang_shang, "干上神之上神"),
        _mk_ke("第三课", ri_zhi, zhi_shang, "日支上神"),
        _mk_ke("第四课", zhi_shang, zhi_shang_shang, "支上神之上神"),
    ]
    # 八专 / 别责：课有重复时按不备课处理（去掉重复课，保持首次出现）
    seen: set[tuple[str, str]] = set()
    dedup: list[dict] = []
    for k in sike:
        key = (k["lower"], k["upper"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(k)
    sike_for_chuan = dedup if len(dedup) < 4 or (ri_gan, ri_zhi) in BA_ZHUAN_RI else sike

    # ---- 5. 三传 ----
    is_fuyin = (yue_jiang == zhan_shi)
    is_fanyin = tuple(sorted((yue_jiang, zhan_shi))) in {tuple(sorted(p)) for p in LIU_CHONG}

    san = _fa_san_chuan(tian, sike_for_chuan, ri_gan, ri_zhi, gan_shang, zhi_shang,
                        yue_jiang, zhan_shi)

    # 伏吟 / 反吟 且无克贼时，改用专门取法
    has_ke = any(k["relation"] for k in sike_for_chuan)
    if is_fuyin and not has_ke:
        if GAN_YANGYANG[ri_gan] == "阳":
            chu = gan_shang
        else:
            chu = zhi_shang
        zhong = _xing(chu)
        if zhong == chu:  # 自刑：中传取支上神
            zhong = zhi_shang
        mo = _xing(zhong)
        if mo == zhong:
            mo = gan_shang
        san = {"method": "伏吟法", "keTi": "伏吟课",
               "desc": "月将临占时，天地盘同位，事主静、宜守，动则迟滞。",
               "chu": chu, "zhong": zhong, "mo": mo, "fromKe": "伏吟"}
    elif is_fanyin and not has_ke:
        chu = YI_MA.get(ri_zhi, ri_zhi)
        san = {"method": "反吟法", "keTi": "反吟课（无依）",
               "desc": "月将与占时相冲，反复不定，事多更张，宜速不宜缓。",
               "chu": chu, "zhong": zhi_shang, "mo": gan_shang, "fromKe": "反吟"}

    # ---- 6. 遁干 / 空亡 / 六亲 ----
    xun_table, kong_wang = _xun_gan_table(ri_gan, ri_zhi)

    def _deco(zhi: str) -> dict:
        gan = xun_table.get(zhi, "")
        return {
            "zhi": zhi,
            "gan": gan or "空",
            "liuqin": _liuqin(ri_gan, gan) if gan else "空亡",
            "wuxing": ZHI_WUXING[zhi],
            "kongWang": zhi in kong_wang,
        }

    # ---- 7. 十二天将 ----
    gui_yang, gui_yin = GUI_REN[ri_gan]
    gui_zhi = gui_yang if zhan_shi in DAY_ZHI else gui_yin
    shun = gui_zhi in JIANG_SHUN_ZHI
    start = ZHI.index(gui_zhi)
    tian_jiang = []
    for i, name in enumerate(TIAN_JIANG):
        pos = ZHI[(start + i) % 12] if shun else ZHI[(start - i) % 12]
        tian_jiang.append({
            "zhi": pos,
            "jiang": name,
            "jiXiong": JIANG_JIXIONG[name],
            "desc": JIANG_DESC[name],
        })

    def _jiang_at(zhi: str) -> str:
        for item in tian_jiang:
            if item["zhi"] == zhi:
                return item["jiang"]
        return ""

    # ---- 8. 组装输出 ----
    tian_pan = []
    for z in ZHI:
        up = tian[z]
        tian_pan.append({
            "zhi": z,
            "shen": up,
            "shenName": YUE_JIANG_DESC.get(up, "").split(" · ")[0],
            "gan": xun_table.get(up, ""),
            "liuqin": _liuqin(ri_gan, xun_table.get(up, "")) if xun_table.get(up) else "—",
            "jiang": _jiang_at(z),
            "kongWang": z in kong_wang,
        })

    chuan_detail = []
    for key, label in (("chu", "初传"), ("zhong", "中传"), ("mo", "末传")):
        z = san[key]
        d = _deco(z)
        d.update({"label": label, "jiang": _jiang_at(z),
                  "shenName": YUE_JIANG_DESC.get(z, "").split(" · ")[0]})
        chuan_detail.append(d)

    analysis = (
        f"{jieqi}后{yue_jiang}将（{yue_jiang_name}）加{zhan_shi}时，"
        f"日辰{ri_ganzhi}，日干{ri_gan}寄{ji_gong}宫。"
        f"四课以{san['fromKe']}发用，{san['method']}，课体{san['keTi']}。"
        f"三传 {chuan_detail[0]['zhi']} → {chuan_detail[1]['zhi']} → {chuan_detail[2]['zhi']}"
        f"（{san['desc']}）"
    )

    guide = [
        {"icon": "🎯", "title": "发用", "note": f"{san['fromKe']}发用，{san['method']} · {san['keTi']}",
         "color": "#d4a853"},
        {"icon": "🌗", "title": "初传（事之始）",
         "note": f"{chuan_detail[0]['zhi']}{chuan_detail[0]['gan']} · {chuan_detail[0]['jiang']} · {chuan_detail[0]['liuqin']}",
         "color": "#b8a6ff"},
        {"icon": "🌘", "title": "中传（事之中）",
         "note": f"{chuan_detail[1]['zhi']}{chuan_detail[1]['gan']} · {chuan_detail[1]['jiang']} · {chuan_detail[1]['liuqin']}",
         "color": "#5ce1e6"},
        {"icon": "🌑", "title": "末传（事之终）",
         "note": f"{chuan_detail[2]['zhi']}{chuan_detail[2]['gan']} · {chuan_detail[2]['jiang']} · {chuan_detail[2]['liuqin']}",
         "color": "#4ade80"},
        {"icon": "⚠️", "title": "空亡", "note": "、".join(kong_wang) + " 旬空，落空之事难成",
         "color": "#ff6b6b"},
    ]

    return {
        # BasePaipanResponse 必填三件套（与 qimen / ziwei 同口径）
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "timeText": time_text or ("不详" if hour is None else f"{h}时"),
        "type": "大六壬",
        "jieqi": jieqi,
        "yueJiang": yue_jiang,
        "yueJiangName": yue_jiang_name,
        "yueJiangDesc": YUE_JIANG_DESC.get(yue_jiang_zhi_from_jq or yue_jiang, ""),
        "zhanShi": zhan_shi,
        "riGanZhi": ri_ganzhi,
        "riGan": ri_gan,
        "riZhi": ri_zhi,
        "jiGong": ji_gong,
        "tianPan": tian_pan,
        "siKe": sike,
        "sanChuan": {**san, "items": chuan_detail},
        "kongWang": kong_wang,
        "tianJiang": tian_jiang,
        "guiRen": {"zhi": gui_zhi, "dayNight": "昼贵" if zhan_shi in DAY_ZHI else "夜贵",
                   "shun": shun},
        "fuYin": is_fuyin,
        "fanYin": is_fanyin,
        "analysis": analysis,
        "guide": guide,
        "question": question,
    }
