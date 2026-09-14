# -*- coding: utf-8 -*-
"""八字排盘服务 —— 基于 lunar-python（寿星天文历）。

输出与前端 bugua 页 BaziModule 数据结构对齐：
pillars / shiShen / wuxing / dayun / liunian / analysis / yongshen。
"""

from __future__ import annotations

from datetime import date, datetime

from lunar_python import Solar, Lunar

from .yijing_data import GAN, GAN_WUXING, ZHI, ZHI_HIDE_GAN, ZHI_WUXING

# 地支五行
# 十神关系（日主 vs 他干）
SHI_SHEN_MAP = {
    ("同", "同"): "比肩", ("同", "异"): "劫财",
    ("生我", "同"): "偏印", ("生我", "异"): "正印",
    ("我生", "同"): "食神", ("我生", "异"): "伤官",
    ("克我", "同"): "七杀", ("克我", "异"): "正官",
    ("我克", "同"): "偏财", ("我克", "异"): "正财",
}

# 五行 -> 图标/颜色（供前端渲染；后端只给五行名与百分比）
ELEMENT_CLS = {"木": "el-wood", "火": "el-fire", "土": "el-earth", "金": "el-metal", "水": "el-water"}
ELEMENT_ICON = {"火": "🔥", "水": "💧", "土": "🌍", "木": "🌳", "金": "⚙️"}

# 干支 -> 十神
def _gan_relation(day_gan: str, other_gan: str) -> str:
    """两干之间相对日主的十神（other_gan 相对 day_gan）。"""
    if other_gan == day_gan:
        return "比肩"
    dw, ow = GAN_WUXING[day_gan], GAN_WUXING[other_gan]
    yin_day = GAN.index(day_gan) % 2 == 0  # 甲丙戊庚壬 阳
    yin_other = GAN.index(other_gan) % 2 == 0
    same_yin = (yin_day == yin_other)
    if dw == ow:
        return "比肩" if same_yin else "劫财"
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if sheng.get(dw) == ow:
        rel = "我生"
    elif sheng.get(ow) == dw:
        rel = "生我"
    elif ke.get(dw) == ow:
        rel = "我克"
    else:
        rel = "克我"
    key = (rel, "同" if same_yin else "异")
    return SHI_SHEN_MAP[key]


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


def _wuxing_stats(pillar_gans: list[str], hide_gans: list[list[str]]) -> dict[str, float]:
    """五行加权统计：天干 1.0、地支本气 1.0 / 中气 0.5 / 余气 0.3。"""
    weights: dict[str, float] = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    for g in pillar_gans:
        weights[GAN_WUXING[g]] += 1.0
    for i, hides in enumerate(hide_gans):
        for j, g in enumerate(hides):
            w = 1.0 if j == 0 else (0.5 if j == 1 else 0.3)
            weights[GAN_WUXING[g]] += w
    return weights


def compute_bazi(year: int, month: int, day: int, hour: int | None = None,
                 gender: str = "男", time_text: str = "") -> dict:
    """八字排盘。

    hour: 0-23 小时；None 表示时辰不详（用午时补全但标记）。
    """
    h = hour if hour is not None else 12
    if time_text and hour is None:
        h = _time_to_hour(time_text)

    solar = Solar.fromYmdHms(year, month, day, h, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    gz_year = ec.getYear()
    gz_month = ec.getMonth()
    gz_day = ec.getDay()
    gz_time = ec.getTime()

    day_gan = ec.getDayGan()  # 日主

    # 四柱
    pillar_meta = [
        ("年柱", "祖业", gz_year, ec.getYearShiShenGan(), ec.getYearShiShenZhi(), ec.getYearNaYin(), ec.getYearHideGan()),
        ("月柱", "父母", gz_month, ec.getMonthShiShenGan(), ec.getMonthShiShenZhi(), ec.getMonthNaYin(), ec.getMonthHideGan()),
        ("日柱", "自身", gz_day, "日主", ec.getDayShiShenZhi(), ec.getDayNaYin(), ec.getDayHideGan()),
        ("时柱", "子女", gz_time, ec.getTimeShiShenGan(), ec.getTimeShiShenZhi(), ec.getTimeNaYin(), ec.getTimeHideGan()),
    ]
    pillars = []
    for label, who, gz, ss_gan, ss_zhi, nayin, hide in pillar_meta:
        g1, z1 = gz[0], gz[1]
        el = GAN_WUXING[g1] + ZHI_WUXING[z1]
        is_day = label == "日柱"
        # 注文：天干十神 + "坐" + 地支藏干十神
        zhi_ss = ss_zhi[0] if isinstance(ss_zhi, list) and ss_zhi else ss_zhi
        if isinstance(zhi_ss, str):
            note = f"{ss_gan}坐{zhi_ss}"
        else:
            note = f"{ss_gan}坐{zhi_ss}"
        pillars.append({
            "label": f"{label} · {who}",
            "gan": g1,
            "zhi": z1,
            "el": el,
            "elCls": ELEMENT_CLS[GAN_WUXING[g1]],
            "note": "★ 日主" if is_day else note,
            "gold": is_day,
        })

    # 十神统计（天干 + 地支藏干）
    shishen_count: dict[str, dict] = {}
    ss_order = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
    for gz, ss_gan, hides in [
        (gz_year, ec.getYearShiShenGan(), ec.getYearHideGan()),
        (gz_month, ec.getMonthShiShenGan(), ec.getMonthHideGan()),
        (gz_day, ec.getDayShiShenGan(), ec.getDayHideGan()),
        (gz_time, ec.getTimeShiShenGan(), ec.getTimeHideGan()),
    ]:
        # 天干
        if ss_gan != "日主":
            item = shishen_count.setdefault(ss_gan, {"val": 0, "wuxing": f"{gz[0]}{GAN_WUXING[gz[0]]}"})
            item["val"] += 1
        # 地支藏干
        for g in hides:
            ss2 = _gan_relation(day_gan, g)
            item = shishen_count.setdefault(ss2, {"val": 0, "wuxing": f"{g}{GAN_WUXING[g]}"})
            item["val"] += 1

    shi_shen = []
    for name in ss_order:
        if name in shishen_count:
            shi_shen.append({"name": name, "val": shishen_count[name]["val"], "wuxing": shishen_count[name]["wuxing"]})

    # 五行能量
    all_gans = [gz_year[0], gz_month[0], gz_day[0], gz_time[0]]
    all_hides = [ec.getYearHideGan(), ec.getMonthHideGan(), ec.getDayHideGan(), ec.getTimeHideGan()]
    wuxing_weights = _wuxing_stats(all_gans, all_hides)
    total = sum(wuxing_weights.values()) or 1.0
    wuxing = [
        {"label": k, "pct": round(v / total * 100), "icon": ELEMENT_ICON[k]}
        for k, v in wuxing_weights.items()
    ]

    # 大运 —— 性别归一化：接受中英文/大小写变体，未知值默认男命（与函数签名一致）
    _g = (gender or "").strip().lower()
    _is_male = _g in ("男", "male", "m", "1")
    _is_female = _g in ("女", "female", "f", "0")
    yun = ec.getYun(1 if (_is_male or not _is_female) else 0)
    # 起运信息（专业排盘口径：起运公历时间 + 出生后时长 + 起运虚岁）
    yun_start = yun.getStartSolar()
    qiyun = {
        "date": f"{yun_start.getYear():04d}-{yun_start.getMonth():02d}-{yun_start.getDay():02d}",
        "after": f"{yun.getStartYear()}年{yun.getStartMonth()}个月{yun.getStartDay()}天",
        "age": 0,  # 首个干支大运的起运虚岁，下方填充
    }
    dayun = []
    for dy in yun.getDaYun():
        gz_dy = dy.getGanZhi()
        if not gz_dy:
            continue
        age = dy.getStartAge()
        gan_dy = gz_dy[0]
        ss_dy = _gan_relation(day_gan, gan_dy)
        # 该步大运精确起运时刻：起运年（DaYun.startYear）+ 起运纪念日（首步起运的月/日）
        try:
            start_dt = datetime(dy.getStartYear(), yun_start.getMonth(), yun_start.getDay())
        except ValueError:  # 2月29日等边界
            start_dt = datetime(dy.getStartYear(), yun_start.getMonth(), 28)
        if not qiyun["age"]:
            qiyun["age"] = age
        dayun.append({
            "age": f"{age}-{age + 9}岁",
            "gan": gz_dy,
            "note": f"{ss_dy}运",
            "_start_dt": start_dt,
        })
    # 当前大运高亮：按「起运纪念日」精确判定（专业排盘口径），而非农历虚岁近似——
    # 虚岁法在起运日（多为年中）前后的年份里会把当前大运标错一步。
    today = datetime.now()
    cur_idx = None
    for i, d in enumerate(dayun):
        if d["_start_dt"] <= today:
            cur_idx = i
    for d in dayun:
        d.pop("_start_dt", None)
    if cur_idx is not None and len(dayun) > cur_idx:
        dayun[cur_idx]["gold"] = True
        dayun[cur_idx]["note"] = "★ 当前"
        if cur_idx + 1 < len(dayun):
            dayun[cur_idx + 1]["primary"] = True
            dayun[cur_idx + 1]["note"] = "⭐ 黄金期"
            dayun[cur_idx + 1]["highlight"] = True

    # 流年（以立春为界的当前农历年起，未来 5 年）
    base_year = today.year
    now_lunar = Lunar.fromDate(today)
    jq_table = now_lunar.getJieQiTable()
    li_chun = jq_table.get("立春") if jq_table else None
    if li_chun is not None:
        lc = datetime(li_chun.getYear(), li_chun.getMonth(), li_chun.getDay())
        if today < lc:
            base_year -= 1
    liunian = []
    for i in range(5):
        yr = base_year + i
        lyr = lunar.getYearInGanZhiByYear(yr) if hasattr(lunar, "getYearInGanZhiByYear") else ""
        if not lyr:
            s2 = Solar.fromYmd(yr, 6, 15)
            lyr = s2.getLunar().getYearInGanZhi()
        ss_ln = _gan_relation(day_gan, lyr[0])
        liunian.append({"yr": yr, "gan": lyr, "note": f"{ss_ln}年"})

    # 格局判定（简化规则文案）
    day_wx = GAN_WUXING[day_gan]
    month_zhi = gz_month[1]
    month_wx = ZHI_WUXING[month_zhi]
    analysis = _geju_text(day_gan, day_wx, month_zhi, month_wx, wuxing_weights)

    # 用神喜忌（简化规则）
    yongshen = _yongshen(day_gan, day_wx, month_wx, wuxing_weights)

    # 五行个数（天干+地支本气，不含藏干；与卜易居等主流排盘口径一致）
    wuxing_count = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for gz in (gz_year, gz_month, gz_day, gz_time):
        wuxing_count[GAN_WUXING[gz[0]]] += 1
        wuxing_count[ZHI_WUXING[gz[1]]] += 1
    wuxing_count_list = [{"label": k, "count": v} for k, v in wuxing_count.items()]
    lacking = [k for k, v in wuxing_count.items() if v == 0]

    # 神煞（高频：以日干 / 年支·日支 查，并定位落于四柱哪一柱）
    shensha = _shensha(
        day_gan,
        gz_year[1], gz_month[1], gz_day[1], gz_time[1],
    )

    return {
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "shengxiao": lunar.getYearShengXiao(),
        "timeText": time_text or ("不详" if hour is None else f"{h}时"),
        "dayMaster": day_gan,
        "dayMasterWuxing": day_wx,
        "pillars": pillars,
        "shiShen": shi_shen,
        "wuxing": wuxing,
        "wuxingCount": wuxing_count_list,
        "lacking": lacking,
        "dayun": dayun,
        "liunian": liunian,
        "qiyun": qiyun,
        "analysis": analysis,
        "yongshen": yongshen,
        "shensha": shensha,
    }


def _is_de_ling(day_wx: str, month_wx: str) -> bool:
    """得令：月令五行与日主同类（比劫）或生日主（印）→ 身旺基础。"""
    return month_wx == day_wx or _sheng_wx(day_wx) == month_wx


def _geju_text(day_gan: str, day_wx: str, month_zhi: str, month_wx: str,
               weights: dict[str, float]) -> str:
    """格局判定（简化文案）。"""
    # 得令为身旺首要条件；失令但同党众（≥3.5）也可判旺
    de_ling = _is_de_ling(day_wx, month_wx)
    strong = de_ling or weights[day_wx] >= 3.5
    xi = _sheng_wx(day_wx)  # 生我者（印）
    cai = _ke_wx(day_wx)   # 我克者（财）
    verdict = "身旺" if strong else "身弱"
    use = cai if strong else xi
    return (
        f"{day_gan}日主{day_wx}生于{month_zhi}月（{month_wx}），{'得令' if de_ling else '失令'}，{verdict}。"
        f"喜用神为{use}，行运喜{use}旺之地；忌神为{_ke_wx(use)}。"
        f"命局财官印配置需结合大运综合判断，整体格局{'偏高，可成中上格局' if strong else '稳健，宜循序经营'}。"
    )


def _yongshen(day_gan: str, day_wx: str, month_wx: str, weights: dict[str, float]) -> dict:
    """用神喜忌（得令 + 五行加权综合判定）。"""
    de_ling = _is_de_ling(day_wx, month_wx)
    strong = de_ling or weights[day_wx] >= 3.5
    if strong:
        # 身旺：喜克泄（财/官杀/食伤），忌生扶（印/比劫）
        xi_list = [f"{_ke_wx(day_wx)}（财）", f"{_sheng_of(day_wx)}（食伤）", f"{_ke_me_wx(day_wx)}（官杀）"]
        ji_list = [f"{_sheng_wx(day_wx)}（印）", f"{day_wx}（比劫）"]
    else:
        # 身弱：喜生扶（印/比劫），忌克泄（财/官杀/食伤）
        xi_list = [f"{_sheng_wx(day_wx)}（印）", f"{day_wx}（比劫）"]
        ji_list = [f"{_ke_wx(day_wx)}（财）", f"{_sheng_of(day_wx)}（食伤）", f"{_ke_me_wx(day_wx)}（官杀）"]
    return {"xi": xi_list, "ji": ji_list}


def _sheng(a: str) -> str:
    return {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}[a]


def _ke(a: str) -> str:
    return {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}[a]


def _sheng_wx(wx: str) -> str:
    """生我者（印）。"""
    return {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}[wx]


def _ke_me_wx(wx: str) -> str:
    """克我者（官杀）。

    注：不能写成 _ke_wx(_sheng_wx(wx))（印所克者）——五行轮上印与食伤相隔两位，
    印所克者恒等于食伤，会把官杀错算成食伤的重复项（曾导致喜忌卡永远只显示 4 个五行）。
    """
    return {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}[wx]


def _sheng_of(wx: str) -> str:
    """我生者（食伤）。"""
    return _sheng(wx)


def _ke_wx(wx: str) -> str:
    """我克者（财）。"""
    return _ke(wx)


# ===== 神煞（高频子集：天乙贵人/文昌/桃花/驿马/华盖/禄神/羊刃/空亡）=====
# 以日干 / 年支·日支 查神煞目标地支，并定位落于四柱哪一柱（命中则标柱名，否则待引动）

# 天乙贵人（日干）：甲戊庚牛羊、乙己鼠猴乡、丙丁猪鸡位、壬癸兔蛇藏、六辛逢马虎
_GUIREN = {
    "甲": "丑未", "戊": "丑未", "庚": "丑未",
    "乙": "子申", "己": "子申",
    "丙": "亥酉", "丁": "亥酉",
    "壬": "卯巳", "癸": "卯巳",
    "辛": "午寅",
}
# 文昌（日干）：甲乙巳午、丙戊申、丁己酉、庚亥、辛子、壬寅、癸卯
_WENCHANG = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申", "己": "酉",
    "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}
# 桃花/咸池（年支·日支三合局沐浴位）
_TAOHUA = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "亥": "子", "卯": "子", "未": "子",
    "巳": "午", "酉": "午", "丑": "午",
}
# 驿马（年支·日支三合局对冲）
_YIMA = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "亥": "巳", "卯": "巳", "未": "巳",
    "巳": "亥", "酉": "亥", "丑": "亥",
}
# 华盖（年支·日支三合局墓库）
_HUAGAI = {
    "寅": "戌", "午": "戌", "戌": "戌",
    "申": "辰", "子": "辰", "辰": "辰",
    "巳": "丑", "酉": "丑", "丑": "丑",
    "亥": "未", "卯": "未", "未": "未",
}
# 禄神（日干禄地）
_LUSHEN = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳", "己": "午",
    "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}
# 羊刃（日干禄前一位）
_YANGREN = {
    "甲": "卯", "乙": "辰", "丙": "午", "丁": "未", "戊": "午", "己": "未",
    "庚": "酉", "辛": "戌", "壬": "子", "癸": "丑",
}
# 空亡：按日干所属旬（甲1..癸10）
_KONGWANG = {
    1: ("戌", "亥"), 2: ("申", "酉"), 3: ("午", "未"), 4: ("辰", "巳"),
    5: ("寅", "卯"), 6: ("子", "丑"), 7: ("戌", "亥"), 8: ("申", "酉"),
    9: ("午", "未"), 10: ("辰", "巳"),
}
_GAN_IDX = {g: i + 1 for i, g in enumerate(GAN)}  # 甲1..癸10


def _shensha(day_gan: str, year_zhi: str, month_zhi: str, day_zhi: str, time_zhi: str) -> list[dict]:
    """高频神煞：返回 [{name, zhi, pillar, desc}]。

    pillar：神煞目标地支在四柱中的落点（年/月/日/时柱），未命中则「待大运流年引动」。
    """
    zhi_pillar = {year_zhi: "年柱", month_zhi: "月柱", day_zhi: "日柱", time_zhi: "时柱"}

    def _pick(zhis: list[str]) -> tuple[str, str]:
        for z in zhis:
            if z in zhi_pillar:
                return z, zhi_pillar[z]
        return zhis[0], "待大运流年引动"

    items: list[dict] = []
    z, p = _pick(list(_GUIREN[day_gan]))
    items.append({"name": "天乙贵人", "zhi": z, "pillar": p,
                  "desc": "遇危难得人相助，贵人多、转圜之机。"})
    z, p = _pick([_WENCHANG[day_gan]])
    items.append({"name": "文昌", "zhi": z, "pillar": p,
                  "desc": "利学业文书与文职，聪明好学、才思敏捷。"})
    z, p = _pick([_TAOHUA[day_zhi]])
    items.append({"name": "桃花", "zhi": z, "pillar": p,
                  "desc": "主人缘情缘与才艺风流，亦需防感情纷扰。"})
    z, p = _pick([_YIMA[day_zhi]])
    items.append({"name": "驿马", "zhi": z, "pillar": p,
                  "desc": "主变动远行奔波，动中求成、宜向外发展。"})
    z, p = _pick([_HUAGAI[day_zhi]])
    items.append({"name": "华盖", "zhi": z, "pillar": p,
                  "desc": "主孤高才艺、宗教玄学缘分，性喜独处探幽。"})
    z, p = _pick([_LUSHEN[day_gan]])
    items.append({"name": "禄神", "zhi": z, "pillar": p,
                  "desc": "主衣食俸禄与根基安稳，得位则福厚。"})
    z, p = _pick([_YANGREN[day_gan]])
    items.append({"name": "羊刃", "zhi": z, "pillar": p,
                  "desc": "主刚烈决断，亦主损伤风险，宜制不宜纵。"})
    z, p = _pick(list(_KONGWANG[_GAN_IDX[day_gan]]))
    items.append({"name": "空亡", "zhi": z, "pillar": p,
                  "desc": "主虚浮落空，所临之事易成空、宜务实忌浮。"})
    return items
