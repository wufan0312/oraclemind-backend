# -*- coding: utf-8 -*-
"""《周易》64 卦数据 —— 京房八宫体系（六爻 / 梅花易数共用）。

数据来源：京房八宫卦序 + 纳甲法 + 世应规律，均为传统固定数据。

- 八卦先天序：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8
- 每宫五行：乾兑金 / 离火 / 震巽木 / 坎水 / 艮坤土
- 世位规则：本宫6、一世4、二世5、三世6、四世1、五世2、游魂3、归魂3
- 应位 = (世 + 2) % 6 + 1
- 纳甲：每宫固定六爻干支（自下而上）
"""

from __future__ import annotations

# ===== 天干地支 =====
GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
# 地支藏干（本气在前，用于五行统计）
ZHI_HIDE_GAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"], "午": ["丁", "己"], "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"], "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

# ===== 八宫基本信息 =====
GONG_WUXING = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}

# 每宫纳甲（自下而上六爻地支；天干按内/外卦定）
# 内卦（下三爻）干：乾甲 坎戊 艮丙 震庚 巽辛 离己 坤乙 兑丁
# 外卦（上三爻）干：乾壬 坎戊 艮丙 震庚 巽辛 离己 坤癸 兑丁
GONG_NAJIA_ZHI = {
    "乾": ["子", "寅", "辰", "午", "申", "戌"],
    "坎": ["寅", "辰", "午", "申", "戌", "子"],
    "艮": ["辰", "午", "申", "戌", "子", "寅"],
    "震": ["子", "寅", "辰", "午", "申", "戌"],
    "巽": ["丑", "亥", "酉", "未", "巳", "卯"],
    "离": ["卯", "丑", "亥", "酉", "未", "巳"],
    "坤": ["未", "巳", "卯", "丑", "亥", "酉"],
    "兑": ["巳", "卯", "丑", "亥", "酉", "未"],
}
# 内卦（下卦）天干
INNER_GAN = {"乾": "甲", "坎": "戊", "艮": "丙", "震": "庚", "巽": "辛", "离": "己", "坤": "乙", "兑": "丁"}
# 外卦（上卦）天干
OUTER_GAN = {"乾": "壬", "坎": "戊", "艮": "丙", "震": "庚", "巽": "辛", "离": "己", "坤": "癸", "兑": "丁"}

# ===== 64 卦 =====
# 每宫 8 卦：本宫 -> 一世 -> 二世 -> 三世 -> 四世 -> 五世 -> 游魂 -> 归魂
# 字段：name 卦名 | upper 上卦 | lower 下卦 | gong 所属宫 | desc 一句话卦意
_HEXAGRAMS_BY_GONG: dict[str, list[dict]] = {
    "乾": [
        {"name": "乾为天", "upper": "乾", "lower": "乾", "desc": "纯阳刚健，自强不息"},
        {"name": "天风姤", "upper": "乾", "lower": "巽", "desc": "阴遇阳合，不期而遇"},
        {"name": "天山遁", "upper": "乾", "lower": "艮", "desc": "君子远遁，退避保全"},
        {"name": "天地否", "upper": "乾", "lower": "坤", "desc": "天地不交，闭塞不通"},
        {"name": "风地观", "upper": "巽", "lower": "坤", "desc": "观仰俯察，明察秋毫"},
        {"name": "山地剥", "upper": "艮", "lower": "坤", "desc": "剥落侵削，顺势止息"},
        {"name": "火地晋", "upper": "离", "lower": "坤", "desc": "旭日东升，晋升前进"},
        {"name": "火天大有", "upper": "离", "lower": "乾", "desc": "火照上天，大有所获"},
    ],
    "坎": [
        {"name": "坎为水", "upper": "坎", "lower": "坎", "desc": "重险叠陷，诚信渡险"},
        {"name": "水泽节", "upper": "坎", "lower": "兑", "desc": "泽上有水，节制有度"},
        {"name": "水雷屯", "upper": "坎", "lower": "震", "desc": "初生艰难，蓄势待发"},
        {"name": "水火既济", "upper": "坎", "lower": "离", "desc": "水火相济，事已成定"},
        {"name": "泽火革", "upper": "兑", "lower": "离", "desc": "变革更新，顺天应人"},
        {"name": "雷火丰", "upper": "震", "lower": "离", "desc": "雷电皆至，丰盛光明"},
        {"name": "地火明夷", "upper": "坤", "lower": "离", "desc": "光明入地，韬光养晦"},
        {"name": "地水师", "upper": "坤", "lower": "坎", "desc": "地中有水，兴师动众"},
    ],
    "艮": [
        {"name": "艮为山", "upper": "艮", "lower": "艮", "desc": "两山并立，止而有定"},
        {"name": "山火贲", "upper": "艮", "lower": "离", "desc": "山下有火，文饰美化"},
        {"name": "山天大畜", "upper": "艮", "lower": "乾", "desc": "天在山中，厚积薄发"},
        {"name": "山泽损", "upper": "艮", "lower": "兑", "desc": "损下益上，减损为益"},
        {"name": "火泽睽", "upper": "离", "lower": "兑", "desc": "上火下泽，乖离求同"},
        {"name": "天泽履", "upper": "乾", "lower": "兑", "desc": "如履虎尾，谨慎行事"},
        {"name": "风泽中孚", "upper": "巽", "lower": "兑", "desc": "诚信发于中，感通万物"},
        {"name": "风山渐", "upper": "巽", "lower": "艮", "desc": "循序渐进，积跬致远"},
    ],
    "震": [
        {"name": "震为雷", "upper": "震", "lower": "震", "desc": "雷声震动，奋发图强"},
        {"name": "雷地豫", "upper": "震", "lower": "坤", "desc": "雷出地奋，喜悦安乐"},
        {"name": "雷水解", "upper": "震", "lower": "坎", "desc": "雷雨作解，困难消解"},
        {"name": "雷风恒", "upper": "震", "lower": "巽", "desc": "雷风相与，恒久不变"},
        {"name": "地风升", "upper": "坤", "lower": "巽", "desc": "地中生木，步步高升"},
        {"name": "水风井", "upper": "坎", "lower": "巽", "desc": "木上有水，养人无穷"},
        {"name": "泽风大过", "upper": "兑", "lower": "巽", "desc": "泽灭木舟，非常之举"},
        {"name": "泽雷随", "upper": "兑", "lower": "震", "desc": "泽中有雷，随顺时势"},
    ],
    "巽": [
        {"name": "巽为风", "upper": "巽", "lower": "巽", "desc": "风行无孔，谦逊入微"},
        {"name": "风天小畜", "upper": "巽", "lower": "乾", "desc": "风行天上，小有积蓄"},
        {"name": "风火家人", "upper": "巽", "lower": "离", "desc": "风自火出，各安其位"},
        {"name": "风雷益", "upper": "巽", "lower": "震", "desc": "风雷相激，损上益下"},
        {"name": "天雷无妄", "upper": "乾", "lower": "震", "desc": "无妄而行，顺其自然"},
        {"name": "火雷噬嗑", "upper": "离", "lower": "震", "desc": "咬合断隔，明法决断"},
        {"name": "山雷颐", "upper": "艮", "lower": "震", "desc": "山下有雷，颐养正道"},
        {"name": "山风蛊", "upper": "艮", "lower": "巽", "desc": "山下有风，整顿积弊"},
    ],
    "离": [
        {"name": "离为火", "upper": "离", "lower": "离", "desc": "光明相继，附丽中正"},
        {"name": "火山旅", "upper": "离", "lower": "艮", "desc": "山上有火，行旅漂泊"},
        {"name": "火风鼎", "upper": "离", "lower": "巽", "desc": "木上有火，鼎新革故"},
        {"name": "火水未济", "upper": "离", "lower": "坎", "desc": "火水未交，事未成也"},
        {"name": "山水蒙", "upper": "艮", "lower": "坎", "desc": "山下出泉，启蒙开智"},
        {"name": "风水涣", "upper": "巽", "lower": "坎", "desc": "风行水上，涣散而聚"},
        {"name": "天水讼", "upper": "乾", "lower": "坎", "desc": "天与水违，争讼慎始"},
        {"name": "天火同人", "upper": "乾", "lower": "离", "desc": "与人和同，志同道合"},
    ],
    "坤": [
        {"name": "坤为地", "upper": "坤", "lower": "坤", "desc": "厚德载物，柔顺利贞"},
        {"name": "地雷复", "upper": "坤", "lower": "震", "desc": "一阳来复，生机再现"},
        {"name": "地泽临", "upper": "坤", "lower": "兑", "desc": "泽上有地，临事而治"},
        {"name": "地天泰", "upper": "坤", "lower": "乾", "desc": "天地交泰，上下和同"},
        {"name": "雷天大壮", "upper": "震", "lower": "乾", "desc": "雷在天上，刚健强盛"},
        {"name": "泽天夬", "upper": "兑", "lower": "乾", "desc": "泽上于天，决然去除"},
        {"name": "水天需", "upper": "坎", "lower": "乾", "desc": "云上于天，等待时机"},
        {"name": "水地比", "upper": "坎", "lower": "坤", "desc": "水行地上，亲比团结"},
    ],
    "兑": [
        {"name": "兑为泽", "upper": "兑", "lower": "兑", "desc": "两泽相连，喜悦沟通"},
        {"name": "泽水困", "upper": "兑", "lower": "坎", "desc": "泽中无水，困顿守志"},
        {"name": "泽地萃", "upper": "兑", "lower": "坤", "desc": "泽上于地，荟萃聚集"},
        {"name": "泽山咸", "upper": "兑", "lower": "艮", "desc": "山上有泽，感应相通"},
        {"name": "水山蹇", "upper": "坎", "lower": "艮", "desc": "山上有水，行路艰难"},
        {"name": "地山谦", "upper": "坤", "lower": "艮", "desc": "地中有山，谦逊受益"},
        {"name": "雷山小过", "upper": "震", "lower": "艮", "desc": "山上有雷，小有过越"},
        {"name": "雷泽归妹", "upper": "震", "lower": "兑", "desc": "泽上有雷，婚嫁之象"},
    ],
}

# 索引：按 (upper, lower) -> 卦
_HEXA_INDEX: dict[tuple[str, str], dict] = {}
for _gong, _list in _HEXAGRAMS_BY_GONG.items():
    for _i, _h in enumerate(_list):
        _h["gong"] = _gong
        _h["gongWuxing"] = GONG_WUXING[_gong]
        _h["idx"] = _i  # 0本宫 1一世 2二世 3三世 4四世 5五世 6游魂 7归魂
        _SHI = [6, 4, 5, 6, 1, 2, 3, 3][_i]
        _h["shi"] = _SHI
        _h["ying"] = (_SHI + 2) % 6 + 1
        _HEXA_INDEX[(_h["upper"], _h["lower"])] = _h

# ===== 八卦符号 =====
TRIGRAM_SYMBOL = {"乾": "☰", "兑": "☱", "离": "☲", "震": "☳", "巽": "☴", "坎": "☵", "艮": "☶", "坤": "☷"}
# 六十四卦符号（Unicode，按上下卦定位）
_HEXA_SYMBOLS = {
    ("乾", "乾"): "䷀", ("乾", "巽"): "䷫", ("乾", "艮"): "䷠", ("乾", "坤"): "䷋",
    ("巽", "坤"): "䷓", ("艮", "坤"): "䷖", ("离", "坤"): "䷢", ("离", "乾"): "䷍",
    ("坎", "坎"): "䷜", ("坎", "兑"): "䷻", ("坎", "震"): "䷂", ("坎", "离"): "䷾",
    ("兑", "离"): "䷰", ("震", "离"): "䷶", ("坤", "离"): "䷣", ("坤", "坎"): "䷆",
    ("艮", "艮"): "䷳", ("艮", "离"): "䷕", ("艮", "乾"): "䷙", ("艮", "兑"): "䷨",
    ("离", "兑"): "䷥", ("乾", "兑"): "䷉", ("巽", "兑"): "䷼", ("巽", "艮"): "䷴",
    ("震", "震"): "䷲", ("震", "坤"): "䷏", ("震", "坎"): "䷧", ("震", "巽"): "䷟",
    ("坤", "巽"): "䷭", ("坎", "巽"): "䷯", ("兑", "巽"): "䷛", ("兑", "震"): "䷐",
    ("巽", "巽"): "䷸", ("巽", "乾"): "䷈", ("巽", "离"): "䷤", ("巽", "震"): "䷩",
    ("乾", "震"): "䷘", ("离", "震"): "䷔", ("艮", "震"): "䷚", ("艮", "巽"): "䷑",
    ("离", "离"): "䷝", ("离", "艮"): "䷷", ("离", "巽"): "䷱", ("离", "坎"): "䷿",
    ("艮", "坎"): "䷃", ("巽", "坎"): "䷺", ("乾", "坎"): "䷅", ("乾", "离"): "䷌",
    ("坤", "坤"): "䷁", ("坤", "震"): "䷗", ("坤", "兑"): "䷒", ("坤", "乾"): "䷊",
    ("震", "乾"): "䷡", ("兑", "乾"): "䷪", ("坎", "乾"): "䷄", ("坎", "坤"): "䷇",
    ("兑", "兑"): "䷹", ("兑", "坎"): "䷮", ("兑", "坤"): "䷬", ("兑", "艮"): "䷞",
    ("坎", "艮"): "䷦", ("坤", "艮"): "䷎", ("震", "艮"): "䷽", ("震", "兑"): "䷵",
}

# ===== 八卦五行（梅花体用）=====
TRIGRAM_WUXING = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
# 八卦数字（梅花先天数）
TRIGRAM_NUM = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}
NUM_TRIGRAM = {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 8: "坤"}
# 八卦意象
TRIGRAM_MEANING = {
    "乾": "天", "兑": "泽", "离": "火", "震": "雷", "巽": "风", "坎": "水", "艮": "山", "坤": "地",
}

# ===== 五行生克 =====
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def hexagram_by_upper_lower(upper: str, lower: str) -> dict:
    """按上下卦查 64 卦信息。"""
    return _HEXA_INDEX.get((upper, lower))


def hexagram_symbol(upper: str, lower: str) -> str:
    """获取卦的 Unicode 符号。"""
    return _HEXA_SYMBOLS.get((upper, lower), "")


def liuyao_najia(hexagram: dict) -> list[dict]:
    """为卦的 6 爻纳甲（自下而上）。

    返回 [{gan, zhi, wuxing, shishen, text}]：
    - 天干：内卦用宫的内卦干，外卦用宫的外卦干
    - 地支：宫纳甲表
    - 六亲：爻五行 与 宫五行 的六亲关系（生我父母 我生子孙 克我官鬼 我克妻财 比和兄弟）
    """
    gong = hexagram["gong"]
    gong_wx = GONG_WUXING[gong]
    zhis = GONG_NAJIA_ZHI[gong]
    inner_gan = INNER_GAN[gong]
    outer_gan = OUTER_GAN[gong]
    lower_name = hexagram["lower"]
    upper_name = hexagram["upper"]

    lines = []
    for i in range(6):
        gan = inner_gan if i < 3 else outer_gan
        zhi = zhis[i]
        wx = ZHI_WUXING[zhi]
        # 天干五行与地支五行一般同属，纳甲干支五行一致（此处用支五行即可）
        shishen = shishen_of(wx, gong_wx)
        yang = ZHI.index(zhi) % 2 == 0
        text = "━━━" if yang else "━ ━"
        lines.append({
            "gan": gan,
            "zhi": zhi,
            "wuxing": wx,
            "shishen": shishen,
            "text": text,
            "yang": yang,
        })
    return lines


def shishen_of(wuxing: str, gong_wuxing: str) -> str:
    """六亲：爻五行 vs 宫五行。"""
    if wuxing == gong_wuxing:
        return "兄弟"
    if SHENG.get(gong_wuxing) == wuxing:
        return "子孙"  # 我生者
    if SHENG.get(wuxing) == gong_wuxing:
        return "父母"  # 生我者
    if KE.get(gong_wuxing) == wuxing:
        return "妻财"  # 我克者
    return "官鬼"  # 克我者


def gua_to_lines(gua: dict) -> list[bool]:
    """64 卦 -> 六爻阴阳列表（自下而上，True=阳爻）。"""
    # 卦由上下两个三画卦组成，用三个爻编码：阳=1 阴=0
    TRIGRAM_BITS = {
        "乾": [1, 1, 1], "兑": [1, 1, 0], "离": [1, 0, 1], "震": [1, 0, 0],
        "巽": [0, 1, 1], "坎": [0, 1, 0], "艮": [0, 0, 1], "坤": [0, 0, 0],
    }
    return TRIGRAM_BITS[gua["lower"]] + TRIGRAM_BITS[gua["upper"]]


def lines_to_gua(lines: list[bool]) -> tuple[str, str]:
    """六爻阴阳（自下而上）-> (上卦, 下卦)。"""
    TRIGRAM_REV = {
        (1, 1, 1): "乾", (1, 1, 0): "兑", (1, 0, 1): "离", (1, 0, 0): "震",
        (0, 1, 1): "巽", (0, 1, 0): "坎", (0, 0, 1): "艮", (0, 0, 0): "坤",
    }
    lower = TRIGRAM_REV[tuple(lines[0:3])]
    upper = TRIGRAM_REV[tuple(lines[3:6])]
    return upper, lower


# ===== 月令旺相休囚死（五行旺衰表） =====
# 当令者旺、生令者相、令生者休、令克者囚、克令者死
# 月令五行 -> 各五行旺衰
WANG_XIANG = {
    "木": {"木": "旺", "火": "相", "水": "休", "土": "囚", "金": "死"},
    "火": {"火": "旺", "土": "相", "木": "休", "金": "囚", "水": "死"},
    "土": {"土": "旺", "金": "相", "火": "休", "水": "囚", "木": "死"},
    "金": {"金": "旺", "水": "相", "土": "休", "木": "囚", "火": "死"},
    "水": {"水": "旺", "木": "相", "金": "休", "火": "囚", "土": "死"},
}

# 月支 -> 月令五行（寅卯木 / 巳午火 / 申酉金 / 亥子水 / 辰戌丑未土）
ZHI_WANG = {
    "寅": "木", "卯": "木",
    "巳": "火", "午": "火",
    "申": "金", "酉": "金",
    "亥": "水", "子": "水",
    "辰": "土", "戌": "土", "丑": "土", "未": "土",
}


def wang_shuai_of(wuxing: str, month_zhi: str) -> str:
    """五行在月令的旺相休囚死。"""
    ling = ZHI_WANG.get(month_zhi, "土")
    return WANG_XIANG.get(ling, {}).get(wuxing, "休")


# ===== 旬空（60 甲子旬空表） =====
# 日柱所在旬 -> 空亡地支（两位）
_XUNKONG_MAP = {
    0: ("戌", "亥"),   # 甲子旬
    2: ("申", "酉"),   # 甲戌旬
    4: ("午", "未"),   # 甲申旬
    6: ("辰", "巳"),   # 甲午旬
    8: ("寅", "卯"),   # 甲辰旬
    10: ("子", "丑"),  # 甲寅旬
}


def xunkong_of(day_gan: str, day_zhi: str) -> tuple[str, str]:
    """日干支 -> 当旬空亡地支（两位）。

    原理:同一旬内,天干地支差值 (gan_idx - zhi_idx) mod 12 恒定。
    甲子差 0、甲戌差 2、甲申差 4、甲午差 6、甲辰差 8、甲寅差 10。
    """
    gan_idx = "甲乙丙丁戊己庚辛壬癸".index(day_gan)
    zhi_idx = "子丑寅卯辰巳午未申酉戌亥".index(day_zhi)
    diff = (gan_idx - zhi_idx) % 12
    return _XUNKONG_MAP.get(diff, ("戌", "亥"))


# ===== 本宫卦查询（用于寻伏神） =====
def ben_gong_of(gong: str) -> dict:
    """取某宫的本宫卦（八纯卦，用于查伏神）。

    本宫卦六亲齐全:由宫五行推导,每爻六亲按纳甲地支五行 vs 宫五行计算。
    返回卦信息(含六爻纳甲与六亲)。
    """
    return _HEXA_INDEX.get((gong, gong))


def find_shishen_in_gong(gong: str, target_shishen: str) -> dict | None:
    """在本宫卦中查找指定六亲所在爻,返回该爻的纳甲信息(用于伏神)。

    本宫卦六亲齐全,必定能找到。返回 {pos, gan, zhi, wuxing} 或 None。
    """
    ben = ben_gong_of(gong)
    if not ben:
        return None
    najia = liuyao_najia(ben)
    for i, l in enumerate(najia):
        if l["shishen"] == target_shishen:
            return {
                "pos": i + 1,
                "gan": l["gan"],
                "zhi": l["zhi"],
                "wuxing": l["wuxing"],
            }
    return None


# ===== P1 旺衰 / 动变深度（十二长生 · 进退神 · 墓库 · 月破 · 暗动 · 入墓） =====

# 十二长生起例（五行长生位；水土同宫，土随水长生在申）
_CHANGSHENG_BASE = {"木": "亥", "火": "寅", "金": "巳", "水": "申", "土": "申"}
_CHANGSHENG_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
# 地支序（子=1 ... 亥=12）
_ZHI_SEQ = {z: i + 1 for i, z in enumerate(ZHI)}


def changsheng_table(day_wuxing: str) -> dict[str, str]:
    """以日干五行起十二长生，返回 {地支: 十二长生宫位} 查表。

    十二长生：长生→沐浴→冠带→临官→帝旺→衰→病→死→墓→绝→胎→养。
    水土同宫（土长生在申），故日干为土时与日干为水共用同一张表。

    Args:
        day_wuxing: 日干五行（木/火/土/金/水）。
    Returns:
        十二支 -> 十二长生宫位的映射。
    """
    base_zhi = _CHANGSHENG_BASE.get(day_wuxing, "土")
    start = _ZHI_SEQ[base_zhi]
    # 某地支的十二长生位 = (该支序 - 长生支序) mod 12
    return {z: _CHANGSHENG_ORDER[(_ZHI_SEQ[z] - start) % 12] for z in ZHI}


def changsheng_of(day_wuxing: str, zhi: str) -> str:
    """查某爻地支在日干五行下的十二长生宫位。"""
    return changsheng_table(day_wuxing).get(zhi, "长生")


# 进退神（动爻化出之爻与本位的进退关系）
# 四正（孟→仲，旺相方向）化进；四库（三合局顺逆）化进；反向为化退。
_JIN_SHEN = {
    ("寅", "卯"), ("巳", "午"), ("申", "酉"), ("亥", "子"),
    ("丑", "辰"), ("辰", "未"), ("未", "戌"), ("戌", "丑"),
}


def jin_tui_shen(zhi_ben: str, zhi_bian: str) -> str:
    """动爻本位地支 vs 变爻地支 → 化进 / 化退 / 空串。

    化进主事渐成、化退主渐衰。无进退关系（如跨五行）返回空串。
    """
    if (zhi_ben, zhi_bian) in _JIN_SHEN:
        return "化进"
    if (zhi_bian, zhi_ben) in _JIN_SHEN:
        return "化退"
    return ""


# 墓库：五行所入之墓支（木未 / 火戌 / 金丑 / 水辰 / 土辰）
_MU_ZHI = {"木": "未", "火": "戌", "金": "丑", "水": "辰", "土": "辰"}


def mu_zhi_of(wuxing: str) -> str:
    """五行所入墓库地支。"""
    return _MU_ZHI.get(wuxing, "辰")


# 六冲（月破 / 暗动判定用）
_CHONG = {
    "子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}


def is_chong(zhi_a: str, zhi_b: str) -> bool:
    """两地支是否相冲。"""
    return _CHONG.get(zhi_a) == zhi_b


def is_yue_po(zhi: str, month_zhi: str) -> bool:
    """爻支被月建冲 → 月破（主事破败）。"""
    return is_chong(zhi, month_zhi)


def is_an_dong(zhi: str, wuxing: str, month_zhi: str, day_zhi: str) -> bool:
    """静爻被日辰冲且得月建生扶（旺/相）→ 暗动，吉凶同动爻。

    Args:
        zhi: 静爻地支。
        wuxing: 静爻五行。
        month_zhi: 月建地支（农历月支）。
        day_zhi: 日支。
    """
    if not is_chong(zhi, day_zhi):
        return False
    return wang_shuai_of(wuxing, month_zhi) in ("旺", "相")


def is_hua_mu(zhi_bian: str, wuxing_ben: str) -> bool:
    """动爻化出变爻为自身五行墓库 → 化墓（入墓）。"""
    return zhi_bian == mu_zhi_of(wuxing_ben)


def is_ru_mu(zhi: str, wuxing: str, month_zhi: str, day_zhi: str) -> bool:
    """爻自身地支即为月建或日辰墓库支 → 临墓（入墓）。"""
    mu = mu_zhi_of(wuxing)
    return mu in (month_zhi, day_zhi) and zhi == mu


# ===== P2 特殊卦象 / 全局合冲（游魂归魂 · 反呤伏呤 · 卦身 · 三合六冲） =====

# 卦六冲配对（八纯卦两两相冲）
_GUA_CHONG = {
    "乾": "坤", "坤": "乾",
    "坎": "离", "离": "坎",
    "震": "巽", "巽": "震",
    "艮": "兑", "兑": "艮",
}


def guahun_of(hexagram: dict) -> str:
    """游魂 / 归魂标记（基于八宫序号 idx：6=游魂，7=归魂）。

    游魂主心神不宁、事有游移；归魂主事有归宿、回归本原。
    """
    idx = hexagram.get("idx")
    if idx == 6:
        return "游魂"
    if idx == 7:
        return "归魂"
    return ""


def fan_fu_of(ben: dict, bian: dict | None, has_dong: bool) -> tuple[str, str]:
    """反呤 / 伏呤判定（本卦 vs 变卦）。

    - 反呤：变卦与本卦内外卦均相冲（如乾为天变坤为地），主事反复不定、进退两难。
    - 伏呤：变卦与本卦内外卦完全相同（卦体不变、仅爻动），主事滞塞不进、旧事缠绕；需有动爻方论。
    返回 (反呤标记, 伏呤标记)，无则空串。
    """
    if not bian:
        return "", ""
    upper_chong = _GUA_CHONG.get(bian["upper"]) == ben["upper"]
    lower_chong = _GUA_CHONG.get(bian["lower"]) == ben["lower"]
    fan = "反呤" if (upper_chong and lower_chong) else ""
    fu = "伏呤" if (has_dong and bian["upper"] == ben["upper"] and bian["lower"] == ben["lower"]) else ""
    return fan, fu


def guashen_of(ben: dict, month_zhi: str, day_zhi: str) -> dict:
    """卦身（月卦身 + 日卦身 / 身爻）。

    月卦身起例：世爻为阳（初/三/五爻），从初爻起「子」顺数至月建地支，落处为卦身；
    世爻为阴（二/四/上爻），从初爻起「午」顺数至月建地支，落处为卦身。
    日卦身（身爻）：同例以日辰地支起数（流派有异，此处以日支简化）。
    爻位从 1（初爻）起。
    """
    shi = ben["shi"]
    yang_shi = shi in (1, 3, 5)
    start = "子" if yang_shi else "午"

    def _body_pos(zhi: str) -> int:
        diff = (_ZHI_SEQ[zhi] - _ZHI_SEQ[start]) % 12
        return diff % 6 + 1

    yue_pos = _body_pos(month_zhi)
    ri_pos = _body_pos(day_zhi)
    return {
        "yangShi": yang_shi,
        "yuePos": yue_pos,
        "yueZhi": month_zhi,
        "riPos": ri_pos,
        "riZhi": day_zhi,
        "note": ("世爻为阳，月卦身从初爻起子顺数月建" if yang_shi
                 else "世爻为阴，月卦身从初爻起午顺数月建"),
    }


# 三合局（地支五行局）
_SANHE = {
    "水": ("申", "子", "辰"),
    "木": ("亥", "卯", "未"),
    "火": ("寅", "午", "戌"),
    "金": ("巳", "酉", "丑"),
}


def sanhe_of(zhis: list[str]) -> list[str]:
    """给定一组地支，返回其中已凑齐的三合局（局名=五行）。

    三合局主聚合、成事：申子辰水局、亥卯未木局、寅午戌火局、巳酉丑金局。
    """
    s = set(zhis)
    return [wx for wx, trio in _SANHE.items() if set(trio).issubset(s)]


# 六合（地支两两相合，主和合、羁绊、聚合）
_LIUHE = [
    ("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未"),
]


def liuhe_pairs(zhis: list[str]) -> list[tuple[str, str]]:
    """在给定地支集合中找出出现的六合对。"""
    s = set(zhis)
    return [(a, b) for a, b in _LIUHE if a in s and b in s]


# 六冲（地支两两相冲，主冲突、破散、变动）——单向去重
_LIUCHONG = [
    ("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥"),
]


def liuchong_pairs(zhis: list[str]) -> list[tuple[str, str]]:
    """在给定地支集合中找出出现的六冲对。"""
    s = set(zhis)
    return [(a, b) for a, b in _LIUCHONG if a in s and b in s]


# ===== 纳音五行（六十甲子纳音） =====
# 键：干支组合（如「甲子」）；值：纳音（如「海中金」）。
_NAYIN = {
    "甲子": "海中金", "乙丑": "海中金",
    "丙寅": "炉中火", "丁卯": "炉中火",
    "戊辰": "大林木", "己巳": "大林木",
    "庚午": "路旁土", "辛未": "路旁土",
    "壬申": "剑锋金", "癸酉": "剑锋金",
    "甲戌": "山头火", "乙亥": "山头火",
    "丙子": "涧下水", "丁丑": "涧下水",
    "戊寅": "城头土", "己卯": "城头土",
    "庚辰": "白蜡金", "辛巳": "白蜡金",
    "壬午": "杨柳木", "癸未": "杨柳木",
    "甲申": "井泉水", "乙酉": "井泉水",
    "丙戌": "屋上土", "丁亥": "屋上土",
    "戊子": "霹雳火", "己丑": "霹雳火",
    "庚寅": "松柏木", "辛卯": "松柏木",
    "壬辰": "长流水", "癸巳": "长流水",
    "甲午": "沙中金", "乙未": "沙中金",
    "丙申": "山下火", "丁酉": "山下火",
    "戊戌": "平地木", "己亥": "平地木",
    "庚子": "壁上土", "辛丑": "壁上土",
    "壬寅": "金箔金", "癸卯": "金箔金",
    "甲辰": "覆灯火", "乙巳": "覆灯火",
    "丙午": "天河水", "丁未": "天河水",
    "戊申": "大驿土", "己酉": "大驿土",
    "庚戌": "钗钏金", "辛亥": "钗钏金",
    "壬子": "桑柘木", "癸丑": "桑柘木",
    "甲寅": "大溪水", "乙卯": "大溪水",
    "丙辰": "沙中土", "丁巳": "沙中土",
    "戊午": "天上火", "己未": "天上火",
    "庚申": "石榴木", "辛酉": "石榴木",
    "壬戌": "大海水", "癸亥": "大海水",
}


def nayin_of(gan: str, zhi: str) -> str:
    """按干支取纳音五行（如「甲子」→「海中金」）。无匹配返回空串。"""
    return _NAYIN.get(gan + zhi, "")


# ===== 神煞（六爻/八字常用；以日干、日支起例） =====
# 天乙贵人（日干）：甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎。
_SHENSHA_TIANYI = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
    "辛": ["午", "寅"],
}
# 驿马（日支，三合局首之冲）：申子辰马在寅 / 寅午戌马在申 / 亥卯未马在巳 / 巳酉丑马在亥
_SHENSHA_YIMA = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
                 "亥": "巳", "卯": "巳", "未": "巳", "巳": "亥", "酉": "亥", "丑": "亥"}
# 桃花·咸池（日支）：申子辰在酉 / 寅午戌在卯 / 亥卯未在子 / 巳酉丑在午
_SHENSHA_TAOHUA = {"申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯",
                   "亥": "子", "卯": "子", "未": "子", "巳": "午", "酉": "午", "丑": "午"}
# 文昌（日干）：甲巳乙午 / 丙戊申 / 丁己酉 / 庚亥辛子 / 壬寅癸卯
_SHENSHA_WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
                     "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
# 劫煞（日支，三合局绝位）：申子辰巳 / 寅午戌亥 / 亥卯未申 / 巳酉丑寅
_SHENSHA_JIESHA = {"申": "巳", "子": "巳", "辰": "巳", "寅": "亥", "午": "亥", "戌": "亥",
                   "亥": "申", "卯": "申", "未": "申", "巳": "寅", "酉": "寅", "丑": "寅"}
# 华盖（日支，三合局墓库）：申子辰辰 / 寅午戌戌 / 亥卯未未 / 巳酉丑丑
_SHENSHA_HUAGAI = {"申": "辰", "子": "辰", "辰": "辰", "寅": "戌", "午": "戌", "戌": "戌",
                   "亥": "未", "卯": "未", "未": "未", "巳": "丑", "酉": "丑", "丑": "丑"}

# 神煞中文名（用于前端展示）
SHENSHA_NAMES = {
    "tianyi": "天乙贵人", "yima": "驿马", "taohua": "桃花",
    "wenchang": "文昌", "jiesha": "劫煞", "huagai": "华盖",
}


def shensha_targets(day_gan: str, day_zhi: str) -> dict[str, list[str]]:
    """按日干/日支起神煞，返回 {神煞key: 命中地支列表}。

    贵人、文昌论日干；驿马、桃花、劫煞、华盖论日支。
    """
    return {
        "tianyi": _SHENSHA_TIANYI.get(day_gan, []),
        "yima": [_SHENSHA_YIMA.get(day_zhi)],
        "taohua": [_SHENSHA_TAOHUA.get(day_zhi)],
        "wenchang": [_SHENSHA_WENCHANG.get(day_gan)],
        "jiesha": [_SHENSHA_JIESHA.get(day_zhi)],
        "huagai": [_SHENSHA_HUAGAI.get(day_zhi)],
    }


# ===== 互卦 / 错卦 / 综卦 =====
def hucuo_zong(ben_bits: list[bool]) -> dict[str, tuple[str, str]]:
    """由本卦六爻阴阳（自下而上）求互、错、综三卦的 (上卦, 下卦)。

    - 错卦（complementary）：阴阳全反。
    - 综卦（inverted）：上下翻转（韩非称「反」）。
    - 互卦（mutual）：下卦取二三四爻，上卦取三四五爻。
    """
    cuo = [not b for b in ben_bits]
    zong = list(reversed(ben_bits))
    hu_lower = ben_bits[1:4]
    hu_upper = ben_bits[2:5]
    hu = hu_lower + hu_upper
    return {
        "hu": lines_to_gua(hu),
        "cuo": lines_to_gua(cuo),
        "zong": lines_to_gua(zong),
    }


# ===== 八卦万物类象（梅花易数 · 邵雍《梅花易数》卷一） =====
# 用于梅花"以象断事"：八卦对应天时/地理/人物/人事/身体/动物/静物/方位/数字/五味/五色。
# 键含义：tianshi 天时 / dili 地理 / renwu 人物 / renshi 人事 / shenghti 身体 /
#         dongwu 动物 / wu 静物（器物） / fangwei 方位 / shuzi 数字 / weiwei 五味 / se 五色
LEIXIANG = {
    "乾": {
        "tianshi": "天、冰、雹、霰、寒",
        "dili": "京都、大郡、形胜之地、高亢之所",
        "renwu": "君、父、大人、老人、长者、官宦、名人",
        "renshi": "刚健武勇、果决、多动少静、领导",
        "shenghti": "首、骨、肺",
        "dongwu": "马、天鹅、狮、象",
        "wu": "金玉、宝珠、圆物、木果、刚物、冠",
        "fangwei": "西北",
        "shuzi": "一、四、九",
        "weiwei": "辛、辣",
        "se": "大赤、玄黄",
    },
    "兑": {
        "tianshi": "雨、泽、新月、星",
        "dili": "沼泽、缺池、废井、山崩破裂之地",
        "renwu": "少女、妾、歌妓、巫师、奴仆、口舌之人",
        "renshi": "喜悦、口舌、饮食、娱乐",
        "shenghti": "口、舌、肺、喉",
        "dongwu": "羊、泽中之物",
        "wu": "饮食、刀剑、毁折之物、有口之物、乐器",
        "fangwei": "西",
        "shuzi": "二、四、九",
        "weiwei": "辛、辣",
        "se": "白",
    },
    "离": {
        "tianshi": "日、电、虹、霓、霞、火",
        "dili": "南方、干亢之地、炉冶之所、明窗",
        "renwu": "中女、文人、大腹、目疾者、兵戈之人",
        "renshi": "文明、书画、虚怯、争斗、光明",
        "shenghti": "目、心、上焦",
        "dongwu": "雉、龟、蚌、蟹、螺",
        "wu": "火、书、甲胄、槁木、干燥物、灯笼",
        "fangwei": "南",
        "shuzi": "三、二、七",
        "weiwei": "苦",
        "se": "赤、紫",
    },
    "震": {
        "tianshi": "雷",
        "dili": "东方、树木、闹市、竹林、蕃茂之所",
        "renwu": "长男、将帅、客商、舟人、歌伎",
        "renshi": "起动、怒、虚惊、鼓动、躁进",
        "shenghti": "足、肝、发",
        "dongwu": "龙、蛇、百虫",
        "wu": "鼓、车、木器、苇、笙簧",
        "fangwei": "东",
        "shuzi": "四、三、八",
        "weiwei": "酸",
        "se": "青、绿",
    },
    "巽": {
        "tianshi": "风",
        "dili": "东南方、草木茂秀之所、花果菜园、寺观",
        "renwu": "长女、秀士、寡妇、僧道、工巧之人",
        "renshi": "柔和、进退不果、鼓舞、疑惑",
        "shenghti": "股、肱、气、风疾",
        "dongwu": "鸡、百禽、虫",
        "wu": "木、绳、直物、长物、工巧之器、帆",
        "fangwei": "东南",
        "shuzi": "五、三、八",
        "weiwei": "酸",
        "se": "青绿、碧",
    },
    "坎": {
        "tianshi": "月、雨、雪、露、寒、水",
        "dili": "北方、江湖、溪涧、泉井、卑湿之地",
        "renwu": "中男、江湖之人、舟人、盗贼、商贾",
        "renshi": "险陷卑下、心机、漂泊、隐伏",
        "shenghti": "耳、血、肾",
        "dongwu": "豕、鱼、水中之物",
        "wu": "水、带核之物、柔物、酒器、弓轮",
        "fangwei": "北",
        "shuzi": "一、六",
        "weiwei": "咸",
        "se": "黑、玄",
    },
    "艮": {
        "tianshi": "云、雾、山岚",
        "dili": "东北方、山径、丘陵、高阜、径路",
        "renwu": "少男、闲人、山中人、童子、门役",
        "renshi": "静止、禁止、阻隔、安宁、守成",
        "shenghti": "手、指、骨、鼻、背",
        "dongwu": "狗、虎、鼠、百兽",
        "wu": "土石、瓜果、阍寺、门阙、小石",
        "fangwei": "东北",
        "shuzi": "五、七、十",
        "weiwei": "甘",
        "se": "黄",
    },
    "坤": {
        "tianshi": "地、阴云、雾、温",
        "dili": "西南、田野、乡里、平地、郊原",
        "renwu": "母、老母、后母、农夫、众人、妻",
        "renshi": "柔顺、安静、包容、吝啬、厚载",
        "shenghti": "腹、脾、胃、肉",
        "dongwu": "牛、百兽、牝马",
        "wu": "方物、布帛、釜、瓦器、稼穑、衣裳",
        "fangwei": "西南",
        "shuzi": "八、五、十",
        "weiwei": "甘",
        "se": "黄、黑",
    },
}


def leixiang_of(name: str) -> dict:
    """取某八卦的万物类象（梅花易数类象体系）。无则返回空 dict。"""
    return LEIXIANG.get(name, {})


# ===== 先后天卦数（梅花应期取数 / 方位定应） =====
# 先天数（乾1兑2离3震4巽5坎6艮7坤8）：梅花起卦与应期取数之基。
# 后天数（洛书：坎1坤2震3巽4中5乾6兑7艮8离9）：应期方位定应、后天数定局用。
_HOUTIAN_NUM = {"坎": 1, "坤": 2, "震": 3, "巽": 4, "乾": 6, "兑": 7, "艮": 8, "离": 9}


def trigram_num(name: str, num_type: str = "xian") -> int:
    """取八卦卦数。

    num_type="xian" 取先天数（默认，梅花起卦/应期主用）；
    num_type="hou" 取后天数（洛书，应期方位定应用）。
    """
    if num_type == "hou":
        return _HOUTIAN_NUM.get(name, TRIGRAM_NUM.get(name, 0))
    return TRIGRAM_NUM.get(name, 0)
