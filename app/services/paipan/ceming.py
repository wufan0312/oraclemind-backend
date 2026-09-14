"""测字 / 姓名五格 / 合婚 —— 服务端权威实现（P2-2）。

此前这套算法只存在于前端 `src/lib/ceming.ts`，无服务端权威、无测试。
这里把**确定性部分**下沉到后端（五格剖象、三才配置、81 数理、生肖/日支合冲、
五行互补），汉字笔画由调用方传入（笔画属字典能力，前端 cnchar 更全），后端只负责算法。

结论仅供娱乐与传统文化参考，不构成任何决策依据。
"""

from __future__ import annotations

# ===== 基础常量 =====

DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZODIAC = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 尾数 → 五行（1,2 木 / 3,4 火 / 5,6 土 / 7,8 金 / 9,0 水）
TAIL_WUXING = {1: "木", 2: "木", 3: "火", 4: "火", 5: "土",
               6: "土", 7: "金", 8: "金", 9: "水", 0: "水"}

# 五行相生（a 生 b）与相克（a 克 b）
SHENG = ["木", "火", "土", "金", "水"]
KE_PAIRS = [("木", "土"), ("土", "水"), ("水", "火"), ("火", "金"), ("金", "木")]

# 生肖（年支）关系
LIU_HE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
LIU_CHONG = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
LIU_HAI = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]
SAN_HE = [("申", "子", "辰"), ("亥", "卯", "未"), ("寅", "午", "戌"), ("巳", "酉", "丑")]
SAN_XING = [("寅", "巳", "申"), ("丑", "未", "戌"), ("子", "卯")]

# 天干五合
GAN_HE = [("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸")]

# 八卦（测字取象，与前端 TRIGRAMS 一致：按码点取模）
TRIGRAMS = [
    ("乾", "☰", "刚健主动"),
    ("兑", "☱", "喜悦口舌"),
    ("离", "☲", "光明附丽"),
    ("震", "☳", "震动奋起"),
    ("巽", "☴", "顺入渗透"),
    ("坎", "☵", "险陷流转"),
    ("艮", "☶", "止静稳固"),
    ("坤", "☷", "厚德载物"),
]

# ===== 81 数理（num, 吉凶, 简释）=====
# 吉凶口径：大吉 / 吉 / 半吉 / 凶 / 大凶
_W81_RAW = [
    (1, "大吉", "太极首领，万物开泰"), (2, "凶", "一身孤节，混沌未定"),
    (3, "大吉", "进取如意，名利双收"), (4, "凶", "破败凶变，身弱短寿"),
    (5, "大吉", "福寿长寿，阴阳和合"), (6, "吉", "安稳吉庆，天赋幸福"),
    (7, "吉", "刚毅果断，独立权威"), (8, "吉", "勤勉刚健，意志坚固"),
    (9, "凶", "破舟入海，兴尽凶始"), (10, "凶", "万事终局，空虚无实"),
    (11, "大吉", "旱苗逢雨，挽回家运"), (12, "凶", "掘井无泉，意志薄弱"),
    (13, "大吉", "智略超群，才艺成功"), (14, "凶", "破兆离散，沦落天涯"),
    (15, "大吉", "福寿圆满，富贵荣誉"), (16, "大吉", "厚重载德，安富尊荣"),
    (17, "吉", "刚强坚操，突破万难"), (18, "吉", "铁镜重磨，有志竟成"),
    (19, "凶", "多难遮云，风云蔽日"), (20, "凶", "屋下藏金，破败衰亡"),
    (21, "大吉", "明月中天，独立权威"), (22, "凶", "秋草逢霜，百事不如"),
    (23, "大吉", "壮丽旭日，发育旺盛"), (24, "大吉", "金钱丰盈，白手起家"),
    (25, "吉", "英俊刚毅，资性聪敏"), (26, "半吉", "变怪奇伟，波澜重叠"),
    (27, "半吉", "欲望无止，宜守宜退"), (28, "凶", "阔水浮萍，遭难离别"),
    (29, "吉", "智谋优异，财利双收"), (30, "半吉", "吉凶参半，浮沉不定"),
    (31, "大吉", "春日花开，智勇得志"), (32, "大吉", "宝马金鞍，侥幸多望"),
    (33, "大吉", "旭日升天，鸾凤相会"), (34, "凶", "破家亡身，灾祸不绝"),
    (35, "吉", "高楼望月，温和平静"), (36, "凶", "风浪不息，侠气薄情"),
    (37, "大吉", "猛虎出林，权威显达"), (38, "半吉", "磨铁成针，技艺有成"),
    (39, "大吉", "富贵荣华，繁荣兴盛"), (40, "半吉", "退安保守，浮沉不定"),
    (41, "大吉", "纯明纯洁，德高望重"), (42, "半吉", "寒蝉在柳，十艺不成"),
    (43, "凶", "散财破产，邪途災危"), (44, "凶", "烦闷懊恼，须眉难展"),
    (45, "大吉", "顺风扬帆，新生泰和"), (46, "凶", "载宝沉舟，浪里淘金"),
    (47, "大吉", "点石成金，开花结果"), (48, "大吉", "古松立鹤，德智兼备"),
    (49, "半吉", "转变吉凶，吉凶难分"), (50, "凶", "小舟入海，吉凶参半"),
    (51, "半吉", "浮沉不一，盛衰交加"), (52, "大吉", "先见之明，光前裕后"),
    (53, "半吉", "内忧外患，盛衰参半"), (54, "凶", "石上栽花，苦难不绝"),
    (55, "半吉", "外祥内苦，先吉后凶"), (56, "凶", "浪里行舟，历尽艰辛"),
    (57, "吉", "寒雪青松，节操坚固"), (58, "吉", "先苦后甘，池柳逢春"),
    (59, "凶", "寒蝉悲风，无有定向"), (60, "凶", "无谋失算，黑暗无光"),
    (61, "吉", "牡丹芙蓉，名利双收"), (62, "凶", "衰败孤独，表里不一"),
    (63, "大吉", "舟归平海，万物化育"), (64, "凶", "骨肉分离，孤独悲愁"),
    (65, "大吉", "巨流归海，富贵长寿"), (66, "凶", "进退维谷，内外不和"),
    (67, "大吉", "通达自成，利路亨通"), (68, "大吉", "顺风吹帆，兴家立业"),
    (69, "凶", "坐立不安，常陷苦难"), (70, "凶", "残菊逢霜，寂寞无气"),
    (71, "半吉", "石上金花，劳而无功"), (72, "凶", "劳苦相伴，先甘后苦"),
    (73, "吉", "志高力微，厚望成真"), (74, "凶", "无用之辈，沉沦逆境"),
    (75, "吉", "退守保安，安稳有余"), (76, "凶", "倾覆离散，虽成必败"),
    (77, "半吉", "半忧半喜，盛衰交替"), (78, "半吉", "晚景凄凉，功名难就"),
    (79, "凶", "云头望月，前途黑暗"), (80, "凶", "遁世隐居，一生孤独"),
    (81, "大吉", "万物回春，最极之数"),
]
NUM_81: dict[int, dict[str, str]] = {
    n: {"ji": ji, "mean": mean} for n, ji, mean in _W81_RAW
}

# 三才配置吉凶（天-人-地 五行组合的粗判：以相生为吉、相克为凶）
_SANCAI_TEXT = {
    "sheng": "三才相生，配置得宜，基础稳固而易得助力。",
    "ke": "三才相克，配置有阻，需以耐性与调和化解冲击。",
    "bi": "三才比和，气势纯粹，宜专精一行以成大器。",
    "mixed": "三才生克夹杂，吉凶互见，宜守中持稳。",
}


def wrap81(n: int) -> int:
    """81 取模：数理只在 1..81 循环；n<=0 视为 1。"""
    if n <= 0:
        return 1
    return ((n - 1) % 81) + 1


def tail_wuxing(n: int) -> str:
    """按尾数取五行（1,2 木 / 3,4 火 / 5,6 土 / 7,8 金 / 9,0 水）。"""
    return TAIL_WUXING[n % 10]


def _wx_rel(a: str, b: str) -> str:
    """a 与 b 的五行关系：sheng（a 生 b）/ ke（相克）/ bi（比和）。"""
    if a == b:
        return "bi"
    if SHENG.index(b) == (SHENG.index(a) + 1) % 5:
        return "sheng"
    if (a, b) in KE_PAIRS or (b, a) in KE_PAIRS:
        return "ke"
    return "sheng"  # b 生 a，也归为「有生助」


# ===== 五格剖象 =====

def compute_wuge(surname_strokes: list[int], given_strokes: list[int]) -> dict:
    """五格剖象（姓/名各字笔画）。

    规则：
      天格 = 单姓（姓笔画+1）/ 复姓（姓笔画之和）  —— 祖先运，不计吉凶
      人格 = 姓末字 + 名首字                        —— 主运
      地格 = 名各字之和；单名则 +1                  —— 前运
      外格 = 总格 − 人格 + 1                        —— 副运（+1 为「假成格」，与前端 ceming.ts 一致）
      总格 = 姓+名全部笔画之和                      —— 后运
    """
    if not surname_strokes or not given_strokes:
        raise ValueError("姓与名的笔画均不能为空")

    tian = sum(surname_strokes) if len(surname_strokes) > 1 else surname_strokes[0] + 1
    ren = surname_strokes[-1] + given_strokes[0]
    di = sum(given_strokes) if len(given_strokes) > 1 else given_strokes[0] + 1
    zong = sum(surname_strokes) + sum(given_strokes)
    wai = zong - ren + 1

    def grid(label: str, role: str, n: int) -> dict:
        k = wrap81(n)
        info = NUM_81[k]
        return {
            "label": label,
            "role": role,
            "num": n,
            "k": k,
            "ji": info["ji"],
            "mean": info["mean"],
            "wuxing": tail_wuxing(n),
        }

    grids = {
        "tian": grid("天格", "祖先运 · 先天禀赋", tian),
        "ren": grid("人格", "性格主轴 · 一生核心", ren),
        "di": grid("地格", "前运 · 青年至中年", di),
        "wai": grid("外格", "人际 · 外在际遇", wai),
        "zong": grid("总格", "后运 · 中晚年总势", zong),
    }

    tian_wx = tail_wuxing(tian)
    ren_wx = tail_wuxing(ren)
    di_wx = tail_wuxing(di)
    r1 = _wx_rel(tian_wx, ren_wx)
    r2 = _wx_rel(ren_wx, di_wx)
    if r1 in ("sheng", "bi") and r2 in ("sheng", "bi"):
        kind = "sheng" if r1 == "sheng" or r2 == "sheng" else "bi"
    elif "ke" in (r1, r2):
        kind = "ke"
    else:
        kind = "mixed"
    three_talent = {
        "tian": tian_wx,
        "ren": ren_wx,
        "di": di_wx,
        "text": _SANCAI_TEXT[kind],
    }

    # 评分：以人格/总格/地格吉凶为主，三才为辅（0-100）
    score = 60
    for key, w in (("ren", 18), ("zong", 14), ("di", 10), ("wai", 6)):
        ji = grids[key]["ji"]
        score += {"大吉": w, "吉": int(w * 0.7), "半吉": 0, "凶": -int(w * 0.8), "大凶": -w}[ji]
    score += {"sheng": 8, "bi": 4, "mixed": 0, "ke": -8}[kind]
    score = max(0, min(100, score))

    return {
        "grids": grids,
        "threeTalent": three_talent,
        "score": score,
        "incomplete": any(s <= 0 for s in [*surname_strokes, *given_strokes]),
    }


# ===== 合婚 =====

def compute_hehun(
    male_zhi: str,
    female_zhi: str,
    male_gan: str | None = None,
    female_gan: str | None = None,
    male_wuxing: dict[str, int] | None = None,
    female_wuxing: dict[str, int] | None = None,
) -> dict:
    """合婚：生肖（年支）六合/六冲/六害/三合/三刑 + 日干五合 + 五行互补。

    male_zhi / female_zhi 为双方年支（生肖地支），必填。
    """
    if male_zhi not in DIZHI or female_zhi not in DIZHI:
        raise ValueError(f"年支必须是十二地支之一：{''.join(DIZHI)}")

    def in_pairs(pairs, a, b):
        return any((a, b) == p[:2] or (b, a) == p[:2] for p in pairs)

    def in_triples(triples, a, b):
        return any(a in t and b in t for t in triples)

    he = in_pairs(LIU_HE, male_zhi, female_zhi)
    chong = in_pairs(LIU_CHONG, male_zhi, female_zhi)
    hai = in_pairs(LIU_HAI, male_zhi, female_zhi)
    sanhe = in_triples(SAN_HE, male_zhi, female_zhi)
    xing = in_triples(SAN_XING, male_zhi, female_zhi)

    gan_he = bool(
        male_gan
        and female_gan
        and any((male_gan, female_gan) == p or (female_gan, male_gan) == p for p in GAN_HE)
    )

    # 生肖结论优先级：六合 > 三合 > 六冲 > 六害 > 三刑 > 平常
    if he:
        verdict, level = "生肖六合", "上吉"
    elif sanhe:
        verdict, level = "生肖三合", "吉"
    elif chong:
        verdict, level = "生肖六冲", "凶"
    elif hai:
        verdict, level = "生肖六害", "凶"
    elif xing:
        verdict, level = "生肖相刑", "凶"
    else:
        verdict, level = "生肖无刑冲合害", "平"

    # 五行互补：双方五行计数相加后，各行的充盈度
    complement = {}
    if male_wuxing and female_wuxing:
        for wx in SHENG:
            m = int(male_wuxing.get(wx, 0))
            f = int(female_wuxing.get(wx, 0))
            total = m + f
            if total >= 4:
                complement[wx] = "两旺"
            elif total == 0:
                complement[wx] = "两缺"
            elif m == 0 or f == 0:
                complement[wx] = "一方缺（可互补）"
            else:
                complement[wx] = "均有"
        missing_both = [wx for wx in SHENG if complement[wx] == "两缺"]
        score_delta = -6 * len(missing_both)
        if any(v == "一方缺（可互补）" for v in complement.values()):
            score_delta += 4
    else:
        missing_both = []
        score_delta = 0

    base = {"上吉": 92, "吉": 80, "平": 66, "凶": 44}[level]
    if gan_he:
        base += 4
    score = max(0, min(100, base + score_delta))

    return {
        "maleZhi": male_zhi,
        "femaleZhi": female_zhi,
        "maleZodiac": ZODIAC[DIZHI.index(male_zhi)],
        "femaleZodiac": ZODIAC[DIZHI.index(female_zhi)],
        "relations": {
            "he": he,
            "chong": chong,
            "hai": hai,
            "sanhe": sanhe,
            "xing": xing,
            "ganHe": gan_he,
        },
        "verdict": verdict,
        "level": level,
        "complement": complement,
        "missingBoth": missing_both,
        "score": score,
    }


# ===== 测字 =====

def compute_cezi(char: str, strokes: int | None = None) -> dict:
    """测字：按码点取五行/卦象/倾向（与前端 analyzeCezi 同口径）。"""
    if not char:
        raise ValueError("请输入一个汉字")
    ch = char[0]
    code = ord(ch)
    element = SHENG[code % 5]
    trigram_name, trigram_sym, trigram_nature = TRIGRAMS[(code >> 2) % 8]
    t = code % 10
    tendency = "顺势可为" if t < 6 else ("守正待时" if t < 9 else "宜静不宜动")
    return {
        "char": ch,
        "element": element,
        "trigram": {"name": trigram_name, "sym": trigram_sym, "nature": trigram_nature},
        "tendency": tendency,
        "strokes": strokes,
        "codePoint": code,
    }
