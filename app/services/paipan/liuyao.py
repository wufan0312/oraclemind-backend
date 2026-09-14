# -*- coding: utf-8 -*-
"""六爻起卦服务 —— 时间起卦 + 京房纳甲体系。

起卦法（传统时间起卦）：
- 上卦 = (年支数 + 农历月 + 农历日) % 8，余 0 取 8
- 下卦 = (年支数 + 农历月 + 农历日 + 时支数) % 8，余 0 取 8
- 动爻 = (年支数 + 农历月 + 农历日 + 时支数) % 6，余 0 取 6
- 变卦 = 本卦动爻阴阳互换

输出与前端 bugua 页 LiuyaoModule 数据结构对齐：
benGua / bianGua / lines（纳甲六亲·世应·动爻）/ yongshen / analysis。
"""

from __future__ import annotations

from lunar_python import Solar

from .yijing_data import (
    GONG_WUXING,
    GAN_WUXING,
    KE,
    SHENG,
    TRIGRAM_SYMBOL,
    ben_gong_of,
    changsheng_of,
    changsheng_table,
    find_shishen_in_gong,
    fan_fu_of,
    guahun_of,
    guashen_of,
    hexagram_by_upper_lower,
    hexagram_symbol,
    is_an_dong,
    is_hua_mu,
    is_ru_mu,
    is_yue_po,
    jin_tui_shen,
    liuchong_pairs,
    liuhe_pairs,
    lines_to_gua,
    liuyao_najia,
    mu_zhi_of,
    nayin_of,
    sanhe_of,
    shensha_targets,
    shishen_of,
    wang_shuai_of,
    xunkong_of,
    hucuo_zong,
)
from .zhouyi_data import gua_ci, yao_ci, yao_title

# 地支序号（子=1 ... 亥=12，用于时间起卦）
_ZHI_ORD = {"子": 1, "丑": 2, "寅": 3, "卯": 4, "辰": 5, "巳": 6, "午": 7, "未": 8, "申": 9, "酉": 10, "戌": 11, "亥": 12}
# 爻位名称（自下而上）
_POS_NAMES = ["初爻", "二爻", "三爻", "四爻", "五爻", "六爻"]

# ===== 六神（青龙/朱雀/勾陈/螣蛇/白虎/玄武）=====
# 纳甲六爻每条爻必配六神：以占卦日干定初爻六神，自下而上顺排。
# 甲乙→青龙、丙丁→朱雀、戊→勾陈、己→螣蛇、庚辛→白虎、壬癸→玄武。
LIUSHEN = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
# 日干 -> 初爻六神序号（basis index）
_LIUSHEN_BASE = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
                 "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}


def liushen_of(day_gan: str) -> list[str]:
    """按日干排出六条爻的六神（自下而上，初爻→六爻）。"""
    base = _LIUSHEN_BASE.get(day_gan, 0)
    return [LIUSHEN[(base + i) % 6] for i in range(6)]


# ===== 手动 / 摇钱起卦的爻编码（自下而上 6 个 int）=====
# 0=少阳(阳静) 1=少阴(阴静) 2=老阳(阳动) 3=老阴(阴动)
YAO_CODE_YANG = {0: True, 1: False, 2: True, 3: False}
YAO_CODE_DONG = {0: False, 1: False, 2: True, 3: True}


# ===== 用神取用规则（传统六爻完整体系） =====
# 五大用神 + 世应 + 特殊事项,覆盖传统占问全部类目
# 字段:类别 / 关键词 / 用神六亲 / 适用性别(None=通用) / 备注
_YONGSHEN_CATEGORIES = [
    # === 求财问利（妻财爻） ===
    ("求财", ["求财", "发财", "赚钱", "盈利", "收入", "薪酬", "工资", "奖金",
              "生意", "买卖", "贸易", "投资", "理财", "股票", "基金", "期货",
              "彩票", "讨债", "借款", "放贷", "竞标", "分红", "回款"], "妻财", None,
     "财物得失、谋利求财"),
    ("财物", ["失物", "寻物", "丢东西", "遗失", "找东西", "失而复得"], "妻财", None,
     "财物遗失、寻物"),

    # === 婚姻感情（按性别分流） ===
    ("男占姻缘", ["婚", "姻", "感情", "恋爱", "对象", "女友", "妻子", "老婆", "正缘",
                "桃花", "复合", "求婚", "求偶", "相亲", "表白", "前任", "暧昧"], "妻财", "男",
     "男占姻缘以妻财为用"),
    ("女占姻缘", ["婚", "姻", "感情", "恋爱", "对象", "男友", "丈夫", "老公", "正缘",
                "桃花", "复合", "求婚", "求偶", "相亲", "表白", "前任", "暧昧"], "官鬼", "女",
     "女占姻缘以官鬼为用"),

    # === 事业功名（官鬼爻） ===
    ("功名事业", ["官", "升职", "升迁", "功名", "仕途", "求职", "事业", "工作",
                "面试", "提拔", "评定", "职称", "名次", "名声", "地位", "名誉",
                "威望", "考公", "考编", "考公务员"], "官鬼", None,
     "功名事业、求职升迁"),
    ("求名", ["名", "名声", "名誉", "威望", "口碑", "人气", "声望"], "官鬼", None,
     "名望声誉"),

    # === 父母长辈（父母爻） ===
    ("父母长辈", ["父", "母", "爹", "娘", "长辈", "祖父母", "外公", "外婆", "爷爷",
                "奶奶", "岳父", "岳母", "公公", "婆婆", "尊长"], "父母", None,
     "尊长安康、父母之事"),
    ("文书合同", ["文书", "合同", "契约", "协议", "书信", "文件", "档案", "文凭",
                "学历", "证书", "签证", "护照", "公告", "通知", "审批", "签"], "父母", None,
     "文书印信、合同契约"),
    ("屋宅车船", ["房", "屋", "宅", "楼", "买车", "车", "船", "装修", "搬家",
                "置业", "买房", "租房", "店铺", "厂房", "土地", "农田", "宿舍"], "父母", None,
     "庇护之物、宅舍舟车"),
    ("考试升学", ["考试", "升学", "高考", "中考", "考研", "考博", "答辩", "毕业",
                "入学", "录取", "测评", "考核", "评级", "成绩"], "父母", None,
     "文书印信、功名考运"),

    # === 子孙晚辈（子孙爻） ===
    ("子女晚辈", ["子", "女", "孩子", "子女", "怀孕", "求子", "生子", "孕育",
                "晚辈", "徒弟", "学生", "下属", "侄", "甥", "儿媳", "徒"], "子孙", None,
     "晚辈福德、子嗣孕育"),
    ("医药疾病", ["病", "疾", "健康", "身体", "服药", "求医", "看病", "手术",
                "康复", "调养", "意外", "灾", "难", "感冒", "发烧", "住院"], "子孙", None,
     "子孙克制官鬼病灾,为医药福神"),
    ("六畜养殖", ["六畜", "养猪", "养鸡", "养牛", "养羊", "宠物", "饲养", "畜牧"], "子孙", None,
     "畜养之物"),

    # === 兄弟同辈（兄弟爻） ===
    ("兄弟朋友", ["兄弟", "姐妹", "朋友", "同事", "同学", "同行", "合伙人",
                "竞争", "对手", "合作", "伙伴", "闺蜜", "哥们", "搭档"], "兄弟", None,
     "同辈劫财、合作竞争"),

    # === 出行行人 ===
    ("出行", ["出行", "出差", "旅游", "远行", "迁徙", "出国", "赴任", "上任",
              "远游", "走", "行"], "妻财", None,
     "出行看行李盘缠（以妻财为用）,兼看世爻旺衰"),
    ("行人归期", ["行人", "远归", "归期", "何时回", "在外", "失联", "走失",
                  "出门", "回家"], None, None,
     "占行人以应爻为用（他人之事）"),

    # === 官非灾祸（官鬼爻） ===
    ("官非诉讼", ["官非", "诉讼", "打官司", "坐牢", "刑", "罚", "逮捕", "拘留",
                "审问", "纠纷", "官司"], "官鬼", None,
     "官鬼为祸、官非压力"),
    ("盗贼邪祟", ["盗", "贼", "偷", "邪祟", "鬼怪", "闹鬼", "诅咒", "中邪",
                "闹邪", "阴气", "诡异"], "官鬼", None,
     "邪鬼贼盗、官鬼为祸"),

    # === 天气占（特殊） ===
    ("天气晴", ["晴", "出太阳", "晴天", "日出"], "子孙", None,
     "子孙为日月晴明"),
    ("天气雨", ["雨", "雪", "雹", "降雨", "雨雪", "下雨", "暴雨"], "父母", None,
     "父母为雨泽覆盖"),
    ("天气风", ["风", "台风", "风暴", "飓风", "刮风"], "兄弟", None,
     "兄弟为风云"),

    # === 自身运气（无关键词命中时的兜底） ===
    ("自身运势", [], None, None,
     "无特定事项,以世爻为主、兼看用神"),
]

# 默认用神（兜底,以世爻为主,用神为辅,此处占自身用世爻）
_DEFAULT_CATEGORY = "自身运势"

# 六亲含义（完整版,含五行属性与吉凶倾向）
_LIUQIN_DETAIL = {
    "兄弟": {
        "meaning": "同辈竞争、合作分利、劫财争财",
        "wuxing": "比和",
        "tendency": "平",
        "role": "克妻财、劫财利,占兄弟朋友为用",
    },
    "子孙": {
        "meaning": "福神、财源、晚辈下属、医药、日月晴明",
        "wuxing": "我生",
        "tendency": "吉",
        "role": "克制官鬼、生扶妻财,为福德之神",
    },
    "父母": {
        "meaning": "庇护、文书、长辈祖业、宅舍舟车、雨泽",
        "wuxing": "生我",
        "tendency": "半吉",
        "role": "生扶兄弟、克制子孙、为辛劳之神",
    },
    "妻财": {
        "meaning": "钱财、妻室、物质所得、奴婢",
        "wuxing": "我克",
        "tendency": "吉",
        "role": "生扶官鬼、克制父母,为财利之神",
    },
    "官鬼": {
        "meaning": "事业功名、官非压力、夫星、病灾、邪祟",
        "wuxing": "克我",
        "tendency": "凶中带吉",
        "role": "生扶父母、克制兄弟、为功名与灾祸双面神",
    },
}

# 保留兼容字段（旧调用可能引用）
_LIUQIN_MEANING = {k: v["meaning"] for k, v in _LIUQIN_DETAIL.items()}

# 五行生克关系字符串（用于日辰关系描述）
_RELATION_TEXT = {
    "同": "比和（同气相求,得令则旺）",
    "生": "生扶（日辰生用神,有生助之力）",
    "被生": "受生（用神生日辰,反泄其气）",
    "克": "克伤（日辰克用神,受制不吉）",
    "被克": "制杀（用神克日辰,反制为吉）",
}


def _time_to_hour(time_text: str) -> int:
    """时辰文本 -> 小时（取时段中点；'不详' 用 12）。"""
    mapping = {
        "子时": 0, "丑时": 2, "寅时": 4, "卯时": 6, "辰时": 8, "巳时": 10,
        "午时": 12, "未时": 14, "申时": 16, "酉时": 18, "戌时": 20, "亥时": 22,
    }
    for k, v in mapping.items():
        if time_text.startswith(k):
            return v
    return 12


def _qigua_numbers(year: int, month: int, day: int, hour: int | None, time_text: str) -> dict:
    """时间起卦：返回年支数、农历月日、时支数、上卦/下卦/动爻（1-8/1-8/1-6）。"""
    h = hour if hour is not None else 12
    if time_text and hour is None:
        h = _time_to_hour(time_text)
    lunar = Solar.fromYmdHms(year, month, day, h, 0, 0).getLunar()

    year_zhi = lunar.getYearZhi()  # 年支（按立春分界，lunar-python 已处理）
    y_z = _ZHI_ORD.get(year_zhi, 1)
    m = lunar.getMonth()
    d = lunar.getDay()
    t_z = _ZHI_ORD.get(lunar.getTimeZhi(), 1)

    total = y_z + m + d
    total2 = total + t_z
    shang = total % 8 or 8  # 上卦先天数
    xia = total2 % 8 or 8   # 下卦先天数
    dong = total2 % 6 or 6  # 动爻位（1-6，自下而上）

    return {
        "yearZhi": year_zhi, "lunarMonth": m, "lunarDay": d, "timeZhi": lunar.getTimeZhi(),
        "shangNum": shang, "xiaNum": xia, "dongYao": dong,
        "calc": f"{y_z}+{m}+{d}={total}→{total}÷8余{total % 8}；+{t_z}={total2}→{total2}÷8余{total2 % 8}、÷6余{total2 % 6}",
    }


def _flip_line(lines: list[bool], dong: int | list[int]) -> list[bool]:
    """动爻（1-6 或列表）阴阳互换，生成变卦爻位。"""
    out = list(lines)
    dongs = dong if isinstance(dong, list) else [dong]
    for d in dongs:
        if 1 <= d <= 6:
            out[d - 1] = not out[d - 1]
    return out


def _hexa_view(hexagram: dict, symbol: str) -> dict:
    """卦 -> 前端视图对象。"""
    return {
        "name": hexagram["name"],
        "symbol": symbol,
        "desc": hexagram["desc"],
        "gong": hexagram["gong"],
        "gongWuxing": hexagram["gongWuxing"],
        "upper": hexagram["upper"],
        "lower": hexagram["lower"],
        "shiPos": hexagram["shi"],
        "yingPos": hexagram["ying"],
    }


def _build_lines(hexagram: dict, dong_list: list[int], ben_bits: list[bool],
                  bian_bits: list[bool], liushen_seq: list[str]) -> list[dict]:
    """六爻明细：纳甲六亲 + 世应 + 动爻/变爻标记 + 六神 + 伏神（自下而上）。

    ben_bits：本卦爻阴阳（True=阳）；bian_bits：变卦爻阴阳（所有动爻位已翻转）；
    dong_list：动爻位列表（自下而上）；liushen_seq：六神（自下而上，与爻序对齐）。
    伏神：每爻下方隐藏的「本宫同位爻」（京房八宫飞伏），用于飞伏可视化（G12）。
    """
    najia = liuyao_najia(hexagram)
    gong_najia = liuyao_najia(ben_gong_of(hexagram["gong"]))  # 本宫卦，供取伏神
    shi = hexagram["shi"]      # 世位 1-6
    ying = hexagram["ying"]    # 应位 1-6
    dong_set = set(dong_list)
    lines = []
    for i, l in enumerate(najia):
        idx = i + 1
        is_dong = idx in dong_set
        ben_yang = ben_bits[i]
        flipped_yang = bian_bits[i]
        is_bian = is_dong and (flipped_yang != ben_yang)
        # yao 类型：变爻用 bian（阴阳互换后的爻形）
        if is_bian:
            yao = "bian"
            text = "━ ━" if flipped_yang else "━━━"
        else:
            yao = "yang" if ben_yang else "yin"
            text = "━━━" if ben_yang else "━ ━"

        name = f"{l['gan']}{l['zhi']}{l['wuxing']} · {l['shishen']}"
        rights = []
        gold = False
        pink = False
        if is_dong:
            rights.append("⭐ 动爻")
            gold = True
        if is_bian:
            rights.append("🔀 变爻")
            pink = True
        if idx == shi:
            rights.append("世爻")
        if idx == ying:
            rights.append("应爻")
        # 伏神（京房八宫飞伏）：本宫卦同位爻
        fu = gong_najia[i]
        lines.append({
            "pos": _POS_NAMES[i],
            "idx": idx,
            "yao": yao,
            "text": text,
            "gan": l["gan"],
            "zhi": l["zhi"],
            "wuxing": l["wuxing"],
            "shishen": l["shishen"],
            "liushen": liushen_seq[i],
            "nayin": nayin_of(l["gan"], l["zhi"]),
            # 飞伏（G12）：飞神=本爻，伏神=本宫同位爻
            "fuGan": fu["gan"],
            "fuZhi": fu["zhi"],
            "fuWuxing": fu["wuxing"],
            "fuShishen": fu["shishen"],
            "name": name,
            "right": " · ".join(rights) if rights else "",
            "gold": gold,
            "pink": pink,
        })
    return lines


def _enrich_lines(lines: list[dict], ben: dict, bian: dict | None,
                  dong_list: list[int], lunar) -> list[dict]:
    """为每爻附加 P1 旺衰/动变深度标记。

    附加字段：changsheng(十二长生) / yuePo(月破) / anDong(暗动) / ruMu(入墓) /
    jinTui(化进/化退) / houtou(回头生克泄耗比和) / huaMu(化墓)。
    动爻的变爻地支/五行取自变卦(bian)的纳甲而非本卦同位，方能体现跨宫的进退神与回头生克。

    Args:
        lines: _build_lines 生成的六爻明细（自下而上）。
        ben: 本卦 hexagram。
        bian: 变卦 hexagram（无动爻时为 None）。
        dong_list: 动爻位列表。
        lunar: lunar-python 农历对象（取日干/月支/日支）。
    Returns:
        附加标记后的 lines（原地修改并返回）。
    """
    day_wuxing = GAN_WUXING.get(lunar.getDayGan(), "土")
    month_zhi = lunar.getMonthZhi()
    day_gan = lunar.getDayGan()
    day_zhi = lunar.getDayZhi()
    cs_table = changsheng_table(day_wuxing)
    # 神煞目标地支（按日干/日支起例），待逐爻比对
    _SHENSHA_LABEL = {
        "tianyi": "天乙贵人", "yima": "驿马", "taohua": "桃花",
        "wenchang": "文昌", "jiesha": "劫煞", "huagai": "华盖",
    }
    ss_targets = shensha_targets(day_gan, day_zhi)
    dong_set = set(dong_list)
    ben_najia = liuyao_najia(ben)
    bian_najia = liuyao_najia(bian) if bian else None
    # 变爻对本位的五行关系 -> 回头生/克/泄/耗/比和
    _HOUTOU = {"生": "回头生", "克": "回头克", "被生": "回头泄", "被克": "回头耗", "同": "回头比和"}

    for l in lines:
        i = l["idx"] - 1
        zhi = l["zhi"]
        wx = l["wuxing"]
        # 十二长生（以日干五行起长生）
        l["changsheng"] = cs_table.get(zhi, "长生")
        # 月破 / 暗动 / 入墓（临墓库支）
        l["yuePo"] = is_yue_po(zhi, month_zhi)
        l["anDong"] = (l["idx"] not in dong_set) and is_an_dong(zhi, wx, month_zhi, day_zhi)
        l["ruMu"] = is_ru_mu(zhi, wx, month_zhi, day_zhi)
        # 神煞（天乙贵人/驿马/桃花/文昌/劫煞/华盖）
        l["shensha"] = [label for key, label in _SHENSHA_LABEL.items()
                        if zhi in (ss_targets.get(key) or [])]
        # 动爻深度：进退神 + 回头生克 + 化墓（变爻纳甲取自变卦）
        if l["idx"] in dong_set and bian_najia:
            ben_line = ben_najia[i]
            bian_line = bian_najia[i]
            l["jinTui"] = jin_tui_shen(ben_line["zhi"], bian_line["zhi"])
            rel = _wuxing_relation(bian_line["wuxing"], ben_line["wuxing"])
            l["houtou"] = _HOUTOU.get(rel, "")
            l["huaMu"] = is_hua_mu(bian_line["zhi"], ben_line["wuxing"])
            # 变出之爻的干支五行（用于前端"动而化出"解说）
            l["bianGan"] = bian_line["gan"]
            l["bianZhi"] = bian_line["zhi"]
            l["bianWuxing"] = bian_line["wuxing"]
        else:
            l["jinTui"] = ""
            l["houtou"] = ""
            l["huaMu"] = False
            l["bianGan"] = ""
            l["bianZhi"] = ""
            l["bianWuxing"] = ""
    return lines


def _build_bian_lines(bian: dict, ben: dict, dong_list: list[int],
                      liushen_seq: list[str], lunar) -> list[dict]:
    """变卦逐爻装卦（G4）：化出之爻的六亲 / 六神 / 旺衰。

    京房六爻规则：
    - 六亲（shishen）固定按【本卦宫五行】推，变卦六亲不随卦变而变（用神体系恒定）。
    - 干支（纳甲）按【变卦自身所属宫】的固定纳甲表取（每卦有固定纳甲）。
    - 旺衰同论月令（旺相休囚死）+ 日辰关系；旬空按日柱查。
    - 六神按占卦日干、自下而上排，与本卦完全一致（六神只随日干爻位走，与卦无关）。

    动爻位在变卦中即「变爻」，高亮标记；变卦本身的世应亦一并标注（仅作装卦呈现）。
    """
    ben_gong_wx = ben["gongWuxing"]
    najia = liuyao_najia(bian)          # 变卦自身宫纳甲（干支/五行）
    dong_set = set(dong_list)
    month_zhi = lunar.getMonthZhi()
    day_gan = lunar.getDayGan()
    day_zhi = lunar.getDayZhi()
    day_wx = GAN_WUXING.get(day_gan, "土")
    _SHENSHA_LABEL = {
        "tianyi": "天乙贵人", "yima": "驿马", "taohua": "桃花",
        "wenchang": "文昌", "jiesha": "劫煞", "huagai": "华盖",
    }
    ss_targets = shensha_targets(day_gan, day_zhi)
    xk1, xk2 = xunkong_of(day_gan, day_zhi)
    lines = []
    for i, l in enumerate(najia):
        idx = i + 1
        wx = l["wuxing"]
        # 六亲固定按本卦宫五行（关键：用神体系不变）
        shishen = shishen_of(wx, ben_gong_wx)
        # 旺衰 + 日辰关系
        strength = wang_shuai_of(wx, month_zhi)
        day_rel = _wuxing_relation(day_wx, wx)
        day_rel_text = _RELATION_TEXT.get(day_rel, day_rel)
        is_empty = l["zhi"] in (xk1, xk2)
        is_bian = idx in dong_set      # 动爻位 -> 变卦中的变爻
        zhi = l["zhi"]
        yang = l["yang"]
        text = "━━━" if yang else "━ ━"
        rights = []
        if is_bian:
            rights.append("变爻")
        if idx == bian["shi"]:
            rights.append("世爻")
        if idx == bian["ying"]:
            rights.append("应爻")
        lines.append({
            "pos": _POS_NAMES[i],
            "idx": idx,
            "yao": "bian" if is_bian else ("yang" if yang else "yin"),
            "text": text,
            "gan": l["gan"],
            "zhi": l["zhi"],
            "wuxing": wx,
            "shishen": shishen,
            "liushen": liushen_seq[i],
            "nayin": nayin_of(l["gan"], l["zhi"]),
            "shensha": [label for key, label in _SHENSHA_LABEL.items()
                        if zhi in (ss_targets.get(key) or [])],
            "strength": strength,
            "dayRelation": day_rel_text,
            "isEmpty": is_empty,
            "emptyNote": (f"空亡（旬空{xk1}{xk2}）" if is_empty else "不空"),
            "isBian": is_bian,
            "right": " · ".join(rights) if rights else "",
        })
    return lines


def _wuxing_relation(a: str, b: str) -> str:
    """a 对 b 的五行关系:同 / 生 / 被生 / 克 / 被克。"""
    if a == b:
        return "同"
    if SHENG.get(a) == b:
        return "生"
    if SHENG.get(b) == a:
        return "被生"
    if KE.get(a) == b:
        return "克"
    return "被克"


def _match_category(question: str, gender: str) -> tuple[str, str | None, str | None, str]:
    """匹配事项类别 -> (类别名, 用神六亲, 适用性别, 备注)。

    婚姻类按性别分流:男占取妻财、女占取官鬼。
    行人归期等无固定用神的事项返回 (类别, None, None, 备注),由调用方走世爻/应爻。
    """
    q = question or ""
    g = gender or "男"
    # 性别敏感类目优先(避免"对象"被通用类目抢匹配)
    for name, kws, ys, sex, note in _YONGSHEN_CATEGORIES:
        if sex is not None and sex != g:
            continue
        if kws and any(k in q for k in kws):
            return name, ys, sex, note
    # 通用类目(性别无关)
    for name, kws, ys, sex, note in _YONGSHEN_CATEGORIES:
        if sex is not None:
            continue
        if kws and any(k in q for k in kws):
            return name, ys, sex, note
    # 兜底:自身运势(以世爻为主)
    return _DEFAULT_CATEGORY, None, None, "无特定事项,以世爻为主、兼看用神"


def _find_yongshen_lines(lines: list[dict], target_shishen: str) -> list[dict]:
    """在卦中找所有符合六亲的爻(用神可能多现)。"""
    return [l for l in lines if l["shishen"] == target_shishen]


def _pick_main_yongshen_line(candidates: list[dict], shi: int, ying: int, dong_list: list[int]) -> dict:
    """用神多现时,按传统优先级取主用神:
    1. 临世应者(临世优先,占自身之事)
    2. 发动者(动则有变,主事)
    3. 阳爻(进神倾向)
    4. 居上位(高位有力)
    """
    if len(candidates) == 1:
        return candidates[0]
    dong_set = set(dong_list)
    # 优先级评分
    def score(l: dict) -> int:
        s = 0
        if l["idx"] == shi:
            s += 100
        if l["idx"] == ying:
            s += 50
        if l["idx"] in dong_set:
            s += 30
        if l["yao"] in ("yang", "bian") and l.get("text", "").startswith("━━━"):
            s += 10
        s += l["idx"]  # 居上位加分
        return s
    return max(candidates, key=score)


def _find_yuan_jin_chou(yongshen_wx: str) -> tuple[str, str, str]:
    """根据用神五行,推算原神/忌神/仇神五行。

    - 原神:生用神者(SHENG[X]=用神,X 即原神)
    - 忌神:克用神者(KE[X]=用神,X 即忌神)
    - 仇神:生忌神者(同时克原神)
    """
    yuan = next(wx for wx, t in SHENG.items() if t == yongshen_wx)
    jin = next(wx for wx, t in KE.items() if t == yongshen_wx)
    chou = next(wx for wx, t in SHENG.items() if t == jin)
    return yuan, jin, chou


def _find_line_by_wuxing(lines: list[dict], wx: str) -> dict | None:
    """按五行找首个匹配爻。"""
    for l in lines:
        if l["wuxing"] == wx:
            return l
    return None


def _pick_yongshen(question: str, gender: str, ben: dict, lines: list[dict],
                   lunar, dong_list: list[int]) -> dict:
    """完整传统用神取用体系。

    实现:
    1. 关键词匹配事项类别(性别敏感类目优先)
    2. 用神取爻(多现按世应/动爻优先级)
    3. 用神不上卦时寻伏神(查本宫卦)
    4. 月令旺相休囚死 + 日辰生扶克泄
    5. 旬空查表
    6. 原神/忌神/仇神识别(生克链)
    7. 世应辅助判断(占自身看世、占他人看应)
    """
    category, ys_name, _, note = _match_category(question, gender)
    shi = ben["shi"]
    ying = ben["ying"]
    feifu = None  # G12 飞伏结构化数据（仅用神不上卦时填充）

    # 行人归期 / 自身运势:无固定六亲用神,以应爻或世爻为主
    use_shi_or_ying = ys_name is None
    if use_shi_or_ying:
        if category == "行人归期":
            main_line = lines[ying - 1]
            ys_name = main_line["shishen"]
            host_note = f"占行人以应爻(第{ying}爻)为主用,临{main_line['shishen']}"
        else:
            # 自身运势:以世爻为主
            main_line = lines[shi - 1]
            ys_name = main_line["shishen"]
            host_note = f"占自身以世爻(第{shi}爻)为主用,临{main_line['shishen']}"
    else:
        # 正常六亲用神:在本卦中寻爻
        candidates = _find_yongshen_lines(lines, ys_name)
        if candidates:
            main_line = _pick_main_yongshen_line(candidates, shi, ying, dong_list)
            host_note = f"用神{ys_name}现于第{main_line['idx']}爻"
        else:
            # 用神不上卦,查本宫卦寻伏神
            fu = find_shishen_in_gong(ben["gong"], ys_name)
            if fu:
                main_line = lines[fu["pos"] - 1]  # 飞神(本卦对应爻位)
                host_note = (f"用神{ys_name}不上卦,伏于本宫{ben['gong']}卦第{fu['pos']}爻"
                             f"（伏神{fu['gan']}{fu['zhi']}{fu['wuxing']}）,飞神为第{fu['pos']}爻{main_line['shishen']}")
                # G12 飞伏可视化结构化数据
                feifu = {
                    "shiShenName": ys_name,
                    "flyPos": fu["pos"],
                    "flyGan": main_line["gan"],
                    "flyZhi": main_line["zhi"],
                    "flyWuxing": main_line["wuxing"],
                    "flyShishen": main_line["shishen"],
                    "fuPos": fu["pos"],
                    "fuGan": fu["gan"],
                    "fuZhi": fu["zhi"],
                    "fuWuxing": fu["wuxing"],
                    "fuShishen": ys_name,
                    "gong": ben["gong"],
                }
            else:
                main_line = lines[0]
                host_note = f"用神{ys_name}未取到,以初爻为参考"
                feifu = None

    detail = _LIUQIN_DETAIL.get(ys_name, {})
    ys_wx = main_line["wuxing"]
    is_dong = main_line["idx"] in dong_list
    is_shi = main_line["idx"] == shi
    is_ying = main_line["idx"] == ying

    # 月令旺衰
    month_zhi = lunar.getMonthZhi()
    strength = wang_shuai_of(ys_wx, month_zhi)

    # 日辰关系
    day_gan = lunar.getDayGan()
    day_zhi = lunar.getDayZhi()
    day_wx = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}[day_gan]
    day_rel = _wuxing_relation(day_wx, ys_wx)
    day_rel_text = _RELATION_TEXT.get(day_rel, day_rel)

    # 旬空
    xk1, xk2 = xunkong_of(day_gan, day_zhi)
    is_empty = main_line["zhi"] in (xk1, xk2)
    empty_note = (f"用神{main_line['zhi']}空亡(旬空:{xk1}{xk2}),有力难施"
                  if is_empty else f"用神不空(旬空:{xk1}{xk2})")

    # 原神/忌神/仇神
    yuan_wx, jin_wx, chou_wx = _find_yuan_jin_chou(ys_wx)
    yuan_line = _find_line_by_wuxing(lines, yuan_wx)
    jin_line = _find_line_by_wuxing(lines, jin_wx)
    chou_line = _find_line_by_wuxing(lines, chou_wx)

    def _line_brief(l: dict | None, role: str, wx: str) -> dict:
        if l is None:
            return {"wuxing": wx, "shishen": "不上卦", "pos": 0, "dong": False, "note": f"({wx}行)不上卦"}
        return {
            "wuxing": wx,
            "shishen": l["shishen"],
            "pos": l["idx"],
            "dong": l["idx"] in dong_list,
            "note": (f"({l['shishen']}·{wx}行)在第{l['idx']}爻"
                     + ("·发动" if l["idx"] in dong_list else "·安静")),
        }

    yuan_info = _line_brief(yuan_line, "原神", yuan_wx)
    jin_info = _line_brief(jin_line, "忌神", jin_wx)
    chou_info = _line_brief(chou_line, "仇神", chou_wx)

    # 世应辅助
    shi_line = lines[shi - 1]
    ying_line = lines[ying - 1]
    shi_note = (f"世爻在第{shi}爻({shi_line['gan']}{shi_line['zhi']}·{shi_line['shishen']})"
                + ("·与用神同位,自身有力" if is_shi else ""))
    ying_note = (f"应爻在第{ying}爻({ying_line['gan']}{ying_line['zhi']}·{ying_line['shishen']})"
                + ("·与用神同位,他人顺遂" if is_ying else ""))

    # 世爻旺衰（P1-1）：世爻代表问卦人自身，须独立于用神单独论断
    shi_wx = shi_line["wuxing"]
    shi_strength = wang_shuai_of(shi_wx, month_zhi)
    shi_day_rel = _wuxing_relation(day_wx, shi_wx)
    shi_day_text = _RELATION_TEXT.get(shi_day_rel, shi_day_rel)
    xk1b, xk2b = xunkong_of(day_gan, day_zhi)
    shi_empty = shi_line["zhi"] in (xk1b, xk2b)
    shi_strength_note = (
        f"世爻{shi_line['gan']}{shi_line['zhi']}（{shi_wx}行）值月令{month_zhi}为「{shi_strength}」"
        f"，日辰「{shi_day_text}」"
        + ("；世爻空亡，自身无力" if shi_empty else "；世爻不空，自身有气")
    )

    # 应爻旺衰（G10）：应爻代表所问之事/对方，与世爻旺衰对比（六爻关键）
    ying_wx = ying_line["wuxing"]
    ying_strength = wang_shuai_of(ying_wx, month_zhi)
    ying_day_rel = _wuxing_relation(day_wx, ying_wx)
    ying_day_text = _RELATION_TEXT.get(ying_day_rel, ying_day_rel)
    xk1c, xk2c = xunkong_of(day_gan, day_zhi)
    ying_empty = ying_line["zhi"] in (xk1c, xk2c)
    ying_strength_note = (
        f"应爻{ying_line['gan']}{ying_line['zhi']}（{ying_wx}行）值月令{month_zhi}为「{ying_strength}」"
        f"，日辰「{ying_day_text}」"
        + ("；应爻空亡，事体虚浮" if ying_empty else "；应爻不空，事体有凭")
    )

    # 用神爻辞（G6）：若用神爻为动爻，附其爻辞
    ys_yang = main_line["yao"] in ("yang", "bian")
    ys_yao_ci = yao_ci(ben["name"], yao_title(main_line["idx"], ys_yang)) if is_dong else ""

    # 综合吉凶倾向
    tendency = detail.get("tendency", "平")
    if is_empty:
        tendency = "用神空亡,事难成"
    elif strength in ("旺", "相") and day_rel in ("同", "生", "被克"):
        tendency = "用神旺相得生扶,事有可成"
    elif strength in ("死", "囚") and day_rel in ("克", "被生"):
        tendency = "用神休囚受克,事多阻碍"

    return {
        "name": ys_name,
        "category": category,
        "meaning": detail.get("meaning", ""),
        "role": detail.get("role", ""),
        "note": note,
        "wuxing": ys_wx,
        "position": main_line["idx"],
        "gan": main_line["gan"],
        "zhi": main_line["zhi"],
        "isDong": is_dong,
        "isShi": is_shi,
        "isYing": is_ying,
        "hostNote": host_note,
        # 旺衰
        "strength": strength,
        "monthZhi": month_zhi,
        "dayGan": day_gan,
        "dayZhi": day_zhi,
        "dayRelation": day_rel_text,
        # 空亡
        "isEmpty": is_empty,
        "emptyNote": empty_note,
        # 原神忌神仇神
        "yuanShen": yuan_info,
        "jiShen": jin_info,
        "chouShen": chou_info,
        # 世应
        "shiNote": shi_note,
        "yingNote": ying_note,
        # 世爻旺衰（P1-1）
        "shiStrength": shi_strength,
        "shiStrengthNote": shi_strength_note,
        "shiEmpty": shi_empty,
        # 应爻旺衰（G10）
        "yingStrength": ying_strength,
        "yingStrengthNote": ying_strength_note,
        "yingEmpty": ying_empty,
        # 飞伏（G12）
        "feifu": feifu,
        # 用神爻辞（G6）
        "yaoCi": ys_yao_ci,
        # 综合
        "tendency": tendency,
    }


def compute_liuyao(year: int, month: int, day: int, hour: int | None = None,
                   gender: str = "男", time_text: str = "", question: str = "",
                   method: str = "time", lines_input: list[int] | None = None) -> dict:
    """六爻起卦排盘。

    method:
      - 'time'  : 时间起卦（默认，沿用传统时间起卦法）
      - 'coin'  : 摇钱法（lines_input 为 6 爻编码，自下而上）
      - 'manual': 手动起卦（同 coin，由前端逐爻指定阴阳与动爻）
    lines_input: 6 个 int（自下而上）：0 少阳(阳静) / 1 少阴(阴静) / 2 老阳(阳动) / 3 老阴(阴动)
    """
    from .yijing_data import NUM_TRIGRAM, gua_to_lines, lines_to_gua

    # 1) 本卦上下卦 + 动爻列表
    if method in ("coin", "manual"):
        if not lines_input or len(lines_input) != 6:
            raise ValueError("coin/manual 模式需提供 6 爻 lines_input（自下而上）")
        ben_bits = [YAO_CODE_YANG.get(v, True) for v in lines_input]
        dong_list = [i + 1 for i, v in enumerate(lines_input) if YAO_CODE_DONG.get(v, False)]
        shang_gua, xia_gua = lines_to_gua(ben_bits)
        qg = {
            "method": method,
            "dongYaos": dong_list,
            "dongYao": dong_list[0] if dong_list else 0,
            "calc": ("起卦：六爻安静" if not dong_list else
                     "起卦：动爻 " + "、".join(f"第{d}爻" for d in dong_list)),
        }
    else:
        qg0 = _qigua_numbers(year, month, day, hour, time_text)
        shang_gua = NUM_TRIGRAM[qg0["shangNum"]]
        xia_gua = NUM_TRIGRAM[qg0["xiaNum"]]
        dong_list = [qg0["dongYao"]]
        qg = {**qg0, "method": "time", "dongYaos": dong_list}

    ben = hexagram_by_upper_lower(shang_gua, xia_gua)
    if ben is None:
        # 兜底：理论上 8x8=64 全命中，不会走到
        raise ValueError("无法匹配卦象（起卦数据异常）")
    ben_lines = _hexa_view(ben, hexagram_symbol(shang_gua, xia_gua))
    ben_lines["guaCi"] = gua_ci(ben["name"])  # G6 本卦卦辞

    # 2) 变卦：所有动爻阴阳互换
    ben_bits = gua_to_lines(ben)
    bian_bits = _flip_line(ben_bits, dong_list)
    b_shang, b_xia = lines_to_gua(bian_bits)
    bian = hexagram_by_upper_lower(b_shang, b_xia)
    bian_view = _hexa_view(bian, hexagram_symbol(b_shang, b_xia)) if bian else None
    if bian_view:
        bian_view["guaCi"] = gua_ci(bian["name"])  # G6 变卦卦辞

    # 3) 六神（按占卦日干，自下而上）
    lunar = Solar.fromYmdHms(year, month, day,
                             hour if hour is not None else
                             (_time_to_hour(time_text) if time_text else 12),
                             0, 0).getLunar()
    liushen_seq = liushen_of(lunar.getDayGan())

    # 4) 六爻明细
    lines = _build_lines(ben, dong_list, ben_bits, bian_bits, liushen_seq)
    # 4.5) 挂接 P1 旺衰/动变深度标记（十二长生·月破·暗动·入墓·进退神·回头生克·化墓）
    lines = _enrich_lines(lines, ben, bian, dong_list, lunar)

    # 4.6) 变卦逐爻装卦（G4）：化出之爻的六亲/六神/旺衰
    bian_lines = _build_bian_lines(bian, ben, dong_list, liushen_seq, lunar) if bian else []

    # 4.7) 动爻爻辞（G6）：为本卦动爻附《周易》爻辞
    dong_set = set(dong_list)
    for l in lines:
        if l["idx"] in dong_set:
            yang = l["yao"] in ("yang", "bian")
            l["yaoCi"] = yao_ci(ben["name"], yao_title(l["idx"], yang))
        else:
            l["yaoCi"] = ""

    # 4.8) 互卦 / 错卦 / 综卦（G9）
    def _hc_view(upper_lower: tuple[str, str]) -> dict:
        hg = hexagram_by_upper_lower(*upper_lower)
        if not hg:
            return {}
        return {
            "name": hg["name"],
            "upper": hg["upper"],
            "lower": hg["lower"],
            "symbol": hexagram_symbol(hg["upper"], hg["lower"]),
            "desc": hg["desc"],
        }
    ben_hc = hucuo_zong(ben_bits)
    bian_hc = hucuo_zong(bian_bits) if bian else None
    gua_bianhua = {
        "ben": {k: _hc_view(v) for k, v in ben_hc.items()},
        "bian": {k: _hc_view(v) for k, v in bian_hc.items()} if bian_hc else None,
    }

    # 5) 用神（取用 + 旺衰 + 旬空 + 原忌仇 + 世应）
    ys = _pick_yongshen(question, gender, ben, lines, lunar, dong_list)

    # 6) 动爻六亲（无动爻时取世爻）
    shi = ben["shi"]
    dong_line = lines[dong_list[0] - 1] if dong_list else lines[shi - 1]
    dong_shishen = dong_line["shishen"]

    # 7) 卦象解读文案
    special = _special_info(ben, bian, lines, dong_list, lunar)
    analysis = _analysis_text(ben, bian, qg, dong_list, dong_line, ys, dong_shishen, gender, lines, lunar, special)

    # 7.5) 应期推断（G5）
    yingqi = _yingqi_info(ys, lines, dong_list, special, lunar, ben)

    return {
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "timeText": time_text or ("不详" if hour is None else f"{hour}时"),
        "method": method,
        "qigua": qg,
        "benGua": ben_lines,
        "bianGua": bian_view,
        "dongYao": qg["dongYao"],
        "dongYaos": dong_list,
        "lines": lines,
        "yongshen": ys,
        "analysis": analysis,
        "special": special,
        "bianLines": bian_lines,
        "guaBianhua": gua_bianhua,
        "yingqi": yingqi,
    }


def _analysis_text(ben: dict, bian: dict | None, qg: dict, dong_list: list[int],
                   dong_line: dict, ys: dict, dong_shishen: str, gender: str,
                   lines: list[dict], lunar, special: dict) -> list[dict]:
    """卦象解读：本卦 / 用神旺衰+世爻旺衰 / 原忌仇 / 动变深度 / 变卦 / 特殊爻象 / AI 建议。"""
    day_wuxing = GAN_WUXING.get(lunar.getDayGan(), "土")
    dong_set = set(dong_list)
    if dong_list:
        dong_pos = "、".join(_POS_NAMES[d - 1] for d in dong_list)
        dong_suffix = "发动"
    else:
        dong_pos = f"第{ben['shi']}爻（世）"
        dong_suffix = "安静"
    gong_wx = ben["gongWuxing"]
    gong_name = ben["gong"]

    # 段1：本卦与用神取用
    p1 = (
        f"本卦「{ben['name']}」（{ben['gong']}宫{gong_wx}，{ben['desc']}）：{dong_pos}{dong_shishen}{dong_suffix}。"
        f"所问属「{ys['category']}」之事，以「{ys['name']}」为用神（{ys['meaning']}）。{ys['hostNote']}，"
        f"用神{ys['gan']}{ys['zhi']}（{ys['wuxing']}行）在第{ys['position']}爻"
        + ("·发动" if ys.get('isDong') else "·安静")
        + ("·临世" if ys.get('isShi') else "")
        + ("·临应" if ys.get('isYing') else "")
        + "。"
    )

    # 段2：用神旺衰 + 世爻旺衰 + 十二长生
    ys_cs = changsheng_of(day_wuxing, ys["zhi"])
    shi_cs = changsheng_of(day_wuxing, lines[ben["shi"] - 1]["zhi"])
    p2 = (
        f"旺衰：用神{ys['wuxing']}行值月令{ys['monthZhi']}为「{ys['strength']}」（临十二长生「{ys_cs}」）；"
        f"日柱{ys['dayGan']}{ys['dayZhi']}对用神「{ys['dayRelation']}」；{ys['emptyNote']}。"
        f"世爻（问卦人自身）：{ys['shiStrengthNote']}（临十二长生「{shi_cs}」）。"
        f"综合:{ys['tendency']}。"
    )

    # 段3：原神忌神仇神
    p3 = (
        f"生克链:原神{ys['yuanShen']['note']}；忌神{ys['jiShen']['note']}；仇神{ys['chouShen']['note']}。"
        f"原神发动则生扶用神,忌神发动则克伤用神,仇神发动则生忌克原,三者综合决定用神强弱。"
    )

    # 段3.5：动变深度（进退神 / 回头生克 / 化墓）
    dong_parts = []
    for l in lines:
        if l["idx"] in dong_set:
            tags = []
            if l.get("jinTui"):
                tags.append(l["jinTui"])
            if l.get("houtou"):
                tags.append(l["houtou"])
            if l.get("huaMu"):
                tags.append("化墓")
            if tags:
                dong_parts.append(f"第{l['idx']}爻{l['shishen']}（{l['gan']}{l['zhi']}）{'·'.join(tags)}")
    p_dong = (
        "动变深度：" + "；".join(dong_parts) + "。"
        "化进主事渐成、化退主渐衰；回头生扶为吉、回头克伤为凶、化墓主事被收纳而迟滞。"
    ) if dong_parts else "动变深度：六爻安静，无动爻可论进退与回头生克。"

    # 段4：变卦
    if bian:
        p4 = (
            f"变卦「{bian['name']}」（{bian['desc']}）：{dong_pos}{dong_suffix}而化,预示事情的发展趋势与转机所在。"
            f"本卦为当下之象,变卦为结局之象——若用神旺相且临世应,则事有可成。"
        )
    else:
        p4 = "本卦六爻安静,无动爻——事态尚未发动,宜静观其变,待机而动。"

    # 段4.5：特殊爻象（暗动 / 月破 / 入墓）
    special_parts = []
    for l in lines:
        tags = []
        if l.get("yuePo"):
            tags.append("月破")
        if l.get("anDong"):
            tags.append("暗动")
        if l.get("ruMu"):
            tags.append("入墓")
        if tags:
            special_parts.append(f"第{l['idx']}爻{l['shishen']}（{l['zhi']}）{'·'.join(tags)}")
    p_special = (
        "特殊爻象：" + "；".join(special_parts) + "。"
        "月破主事破败、暗动吉凶同动爻、入墓主事被掩藏而迟滞。"
    ) if special_parts else "特殊爻象：无月破、暗动、入墓。"

    # 段4.6：卦体特殊（游魂归魂 / 反呤伏呤 / 卦身）
    SANHE_TRIO = {
        "水": ("申", "子", "辰"), "木": ("亥", "卯", "未"),
        "火": ("寅", "午", "戌"), "金": ("巳", "酉", "丑"),
    }
    gh_parts = []
    if special.get("guahun"):
        gh_note = ("游魂主心神游移、事有变数，宜静不宜妄动"
                   if special["guahun"] == "游魂" else
                   "归魂主事有归宿、回归本原，宜守成")
        gh_parts.append(f"本卦为「{special['guahun']}」卦（{gh_note}）")
    if special.get("bianGuahun"):
        gh_parts.append(f"变卦为「{special['bianGuahun']}」卦")
    if special.get("fan"):
        gh_parts.append("本卦变卦内外卦相冲（反呤），事多反复、进退两难")
    if special.get("fu"):
        gh_parts.append("本卦变卦内外卦相同（伏呤），事滞不进、旧事缠绕")
    gs = special.get("guashen", {})
    gh_parts.append(f"卦身：月卦身在第{gs.get('yuePos', 0)}爻（{gs.get('note', '')}）；"
                    f"日卦身在第{gs.get('riPos', 0)}爻")
    p_guahun = "卦体特殊与卦身：" + "；".join(gh_parts) + "。"

    # 段4.7：全局合冲（三合 / 六合 / 六冲）
    hc_parts = []
    if special.get("sanhe"):
        sanhe_cheng = special.get("sanheCheng", {})
        hc_parts.append("三合局：" + "、".join(
            f"{('成局' if sanhe_cheng.get(wx) else '现局待成')}：{wx}局（{'/'.join(SANHE_TRIO[wx])}）"
            for wx in special["sanhe"]))
    if special.get("liuhe"):
        hc_parts.append("六合：" + "、".join(special["liuhe"]) + "（主和合、聚合）")
    if special.get("liuchong"):
        hc_parts.append("六冲：" + "、".join(special["liuchong"]) + "（主冲突、破散）")
    if special.get("involved"):
        hc_parts.append("世应参与：" + "；".join(special["involved"]))
    if not hc_parts:
        hc_parts.append("卦中无三合、六合、六冲成局")
    p_hechong = "全局合冲：" + "；".join(hc_parts) + "。"

    # 段5：世应与AI建议
    p5 = (
        f"世应:{ys['shiNote']}；{ys['yingNote']}。"
        f"世爻旺衰是问卦人自身根基:{ys['shiStrengthNote']}。"
        f"AI 建议:{dong_pos}爻发动主事情正在变化,宜顺势而为、不可强求;"
        f"用神旺相（值月建日辰生扶）则事半功倍,休囚受克则需耐心经营;"
        f"世爻有气则自身可扛事,世爻空破则宜守不宜攻;"
        f"用神空亡宜静待出空之期,忌神发动需防小人/阻碍。"
        f"结合你问的「{ys['name']}」之事,近期以稳妥推进为上,重大决定可再复核奇门/梅花同参。"
    )
    return [
        {"title": "本卦", "text": p1},
        {"title": "用神旺衰", "text": p2},
        {"title": "原忌仇", "text": p3},
        {"title": "动变深度", "text": p_dong},
        {"title": "变卦", "text": p4},
        {"title": "特殊爻象", "text": p_special},
        {"title": "卦体特殊", "text": p_guahun},
        {"title": "全局合冲", "text": p_hechong},
        {"title": "AI 建议", "text": p5},
    ]


def _special_info(ben: dict, bian: dict | None, lines: list[dict],
                  dong_list: list[int], lunar) -> dict:
    """卦体特殊卦象 + 全局合冲（P2）：游魂归魂 / 反呤伏呤 / 卦身 / 三合六冲。

    返回结构化 dict，供解读文案与 AI 注入复用。
    """
    month_zhi = lunar.getMonthZhi()
    day_zhi = lunar.getDayZhi()
    dong_set = set(dong_list)

    # 1) 游魂 / 归魂（本卦 + 变卦）
    guahun = guahun_of(ben)
    bian_guahun = guahun_of(bian) if bian else ""
    # 2) 反呤 / 伏呤
    fan, fu = fan_fu_of(ben, bian, bool(dong_list))
    # 3) 卦身
    gs = guashen_of(ben, month_zhi, day_zhi)

    # 4) 全局合冲：以本卦六爻地支为体（变爻化出之支已在 P1 动变深度中论，不并入避免"虚局全中"）
    ben_zhis = [l["zhi"] for l in lines]
    ben_set = set(ben_zhis)
    dong_zhis = {l["zhi"] for l in lines if l["idx"] in dong_set}
    SANHE_TRIO = {
        "水": ("申", "子", "辰"), "木": ("亥", "卯", "未"),
        "火": ("寅", "午", "戌"), "金": ("巳", "酉", "丑"),
    }
    sanhe = sanhe_of(ben_zhis)
    # 三合局成否：中神必在局中；至少一成员为动爻或临日月方"成局"，否则"现局待成"
    sanhe_cheng = {}
    for wx in sanhe:
        trio = SANHE_TRIO[wx]
        sanhe_cheng[wx] = any(z in dong_zhis or z in (month_zhi, day_zhi) for z in trio)
    liuhe = liuhe_pairs(ben_zhis)
    liuchong = liuchong_pairs(ben_zhis)

    # 世应地支是否参与合冲 / 三合局（增强判断）
    shi_zhi = lines[ben["shi"] - 1]["zhi"] if ben.get("shi") else ""
    ying_zhi = lines[ben["ying"] - 1]["zhi"] if ben.get("ying") else ""
    involved = []
    for z, role in ((shi_zhi, "世爻"), (ying_zhi, "应爻")):
        if not z:
            continue
        for a, b in liuhe:
            if z in (a, b):
                other = b if z == a else a
                involved.append(f"{role}{z}与{other}六合")
        for a, b in liuchong:
            if z in (a, b):
                other = b if z == a else a
                involved.append(f"{role}{z}与{other}六冲")
        for wx in sanhe:
            if z in SANHE_TRIO[wx]:
                involved.append(f"{role}{z}入{wx}局（三合）")

    return {
        "guahun": guahun,
        "bianGuahun": bian_guahun,
        "fan": fan,
        "fu": fu,
        "guashen": gs,
        "sanhe": sanhe,
        "sanheCheng": sanhe_cheng,
        "liuhe": ["".join(p) for p in liuhe],
        "liuchong": ["".join(p) for p in liuchong],
        "involved": involved,
    }


def _yingqi_info(ys: dict, lines: list[dict], dong_list: list[int],
                 special: dict, lunar, ben: dict) -> dict:
    """应期推断（G5）：据用神旺衰 / 旬空 / 月破 / 进退神 / 入墓 / 三合局，给出事成败之时。

    说明：应期为传统六爻经验法则（旺相之期、出空/出破、化进渐成、冲墓出墓、三合局旺），
    多因素交参，此处给出分项提示与综合结论，供参考而非绝对断语。
    """
    month_zhi = lunar.getMonthZhi()
    day_gan = lunar.getDayGan()
    day_zhi = lunar.getDayZhi()
    xk1, xk2 = xunkong_of(day_gan, day_zhi)
    ys_wx = ys["wuxing"]
    strength = ys["strength"]
    is_empty = ys["isEmpty"]
    ys_zhi = ys["zhi"]
    dong_set = set(dong_list)
    points: list[dict] = []

    # 1) 旺衰定基
    if strength in ("旺", "相"):
        base = (f"用神{ys_wx}行值月令{month_zhi}为「{strength}」，得时当令，事在其旺相之期可成——"
                f"多应在{ys_wx}行当令之月或生旺之日。")
    elif strength == "休":
        base = (f"用神{ys_wx}行值月令{month_zhi}为「休」，气不当令，事缓，"
                f"须待生旺之期方能动。")
    else:  # 囚 / 死
        base = (f"用神{ys_wx}行值月令{month_zhi}为「{strength}」，失令受制，事迟阻，"
                f"须待转出旺相方可成。")
    points.append({"label": "旺衰定基", "text": base})

    # 2) 旬空应期
    if is_empty:
        points.append({"label": "旬空应期", "text":
            f"用神{ys_zhi}空亡（旬空{xk1}{xk2}），事体虚悬。应期在「出空」：一为填实（逢{xk1}或{xk2}之日月），"
            f"二为冲空（日辰冲{xk1}/{xk2}），出空则事动。"})
    else:
        points.append({"label": "旬空应期", "text":
            f"用神不空（旬空{xk1}{xk2}），事有凭依，无需待出空。"})

    # 3) 月破应期
    ys_line = next((l for l in lines if l["idx"] == ys["position"]), None)
    if ys_line and ys_line.get("yuePo"):
        points.append({"label": "月破应期", "text":
            f"用神{ys_zhi}月破（被月建{month_zhi}冲），事体破损。应期在「出破」："
            f"填实或逢合（与月建相合）之期方可成。"})
    else:
        points.append({"label": "月破应期", "text": "用神不犯月破，无破败之阻。"})

    # 4) 进退神
    jt_parts = []
    for l in lines:
        if l["idx"] in dong_set:
            if l.get("jinTui") == "化进":
                jt_parts.append(f"第{l['idx']}爻{l['shishen']}化进")
            elif l.get("jinTui") == "化退":
                jt_parts.append(f"第{l['idx']}爻{l['shishen']}化退")
    if jt_parts:
        points.append({"label": "进退神应期", "text":
            "、".join(jt_parts) + "：化进主事渐成、应期渐近；化退主事渐消、成而复退。"})

    # 5) 入墓应期
    mu_parts = []
    for l in lines:
        if l["idx"] in dong_set and l.get("huaMu"):
            mu_parts.append(f"第{l['idx']}爻{l['shishen']}化墓")
        elif l.get("ruMu"):
            mu_parts.append(f"第{l['idx']}爻{l['shishen']}入墓")
    if mu_parts:
        points.append({"label": "入墓应期", "text":
            "、".join(mu_parts) + "：爻入墓库，事被掩藏迟滞；应期在「冲墓/出墓」"
            f"（逢墓库之冲：{mu_zhi_of(ys_wx)}）之期方显。"})

    # 6) 三合局
    if special.get("sanhe"):
        cheng = special.get("sanheCheng", {})
        sanhe_txt = "、".join(
            f"{wx}局（{'已成局' if cheng.get(wx) else '现局待成'}）" for wx in special["sanhe"])
        points.append({"label": "三合应期", "text":
            f"卦见三合：{sanhe_txt}。三合主聚合成事，应期多在局旺之期或逢局中缺支填实（补齐三合）之时。"})

    # 7) 世应对比
    points.append({"label": "世应参考", "text":
        f"世爻（{ys['shiStrengthNote']}）；应爻（{ys['yingStrengthNote']}）。"
        f"世旺应衰则我强彼弱、事易成；应旺世衰则彼强我弱，宜待自身转旺。"})

    # 综合结论
    summary = "应期推断（传统定应期经验法则，供参考，非绝对）："
    if is_empty:
        summary += "用神空亡，先待出空之期；"
    if strength in ("旺", "相"):
        summary += "用神旺相，事在旺相之期可成；"
    elif strength in ("囚", "死"):
        summary += "用神休囚受克，须待转旺方可成；"
    else:
        summary += "用神平休，待生旺之期；"
    if special.get("sanhe"):
        summary += "三合成局则待局旺或补缺之期。"
    summary += "应期受月建、日辰、动变多因素交参，建议结合具体事项细断。"

    return {"summary": summary, "points": points}
