# -*- coding: utf-8 -*-
"""紫微斗数排盘服务 —— 自研安星法。

排盘口径（与传统《紫微斗数全书》一致）：
- 命宫：寅宫起正月顺数至生月，从生月宫起子时逆数至生时
- 身宫：同起点，顺数至生时
- 五行局：命宫干支纳音（金四木三水二火六土五）
- 紫微定位：起寅逆行（水二起寅 / 木三起丑 / 金四起子 / 土五起亥 / 火六起戌）
- 十四主星：紫微星系逆行（天机-1 太阳-3 武曲-4 天同-5 廉贞-8）
             天府星系顺行（太阴+1 贪狼+2 巨门+3 天相+4 天梁+5 七杀+6 破军+10）
- 辅星：左辅右弼 / 文昌文曲 / 天魁天钺 / 禄存擎羊陀罗 / 火星铃星 / 地空地劫
- 四化：生年天干（甲廉破武阳…）
"""

from __future__ import annotations

import datetime

from lunar_python import Solar

from .bazi import _time_to_hour

# ===== 宫位序号：子0 丑1 寅2 卯3 辰4 巳5 午6 未7 申8 酉9 戌10 亥11 =====
ZHI_ORDER = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
GAN_ORDER = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 命盘十二宫（自命宫起逆时针）
PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄", "迁移", "交友", "官禄", "田宅", "福德", "父母"]
PALACE_ICONS = {
    "命宫": "🔮", "兄弟": "👥", "夫妻": "❤️", "子女": "👶", "财帛": "💰", "疾厄": "🏥",
    "迁移": "🎓", "交友": "🤝", "官禄": "💼", "田宅": "🏠", "福德": "🧘", "父母": "👨‍👩‍👧",
}
PALACE_COLORS = {
    "命宫": "var(--accent-gold)", "兄弟": "var(--accent-cyan)", "夫妻": "#a78bfa", "子女": "#ff8e53",
    "财帛": "var(--accent-pink)", "疾厄": "#ff6b6b", "迁移": "var(--accent-gold)", "交友": "var(--accent-cyan)",
    "官禄": "var(--primary-light)", "田宅": "var(--accent-green)", "福德": "var(--accent-gold)", "父母": "var(--accent-green)",
}

# ===== 五行局 =====
JU_BY_NAYIN = {"金": 4, "木": 3, "水": 2, "火": 6, "土": 5}
NAYIN_NAME = [
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
    "泉中水", "屋上土", "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木", "壁上土", "金箔金",
    "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
]
# 60 甲子序号 -> 纳音（每两个一换）
def _nayin(gz_idx: int) -> str:
    return NAYIN_NAME[gz_idx // 2]

def _gz_index(gan: str, zhi: str) -> int:
    """60 甲子序号（n%10=干, n%12=支 的中国剩余定理解）。"""
    gi, zi = GAN_ORDER.index(gan), ZHI_ORDER.index(zhi)
    return (gi * 6 - zi * 5) % 60

# 紫微定位：五行局 -> 起始宫（0-11）
JU_START = {2: 2, 3: 1, 4: 0, 5: 11, 6: 10}  # 水二起寅 / 木三起丑 / 金四起子 / 土五起亥 / 火六起戌

# ===== 十四主星 =====
# 紫微在 X 宫时各主星位置（0-11 制，X=紫微宫位）
def _zhu_star_positions(ziwei_pos: int) -> dict[str, int]:
    tian_fu = 4 - ziwei_pos if ziwei_pos < 5 else 16 - ziwei_pos
    return {
        "紫微": ziwei_pos,
        "天机": (ziwei_pos - 1) % 12,
        "太阳": (ziwei_pos - 3) % 12,
        "武曲": (ziwei_pos - 4) % 12,
        "天同": (ziwei_pos - 5) % 12,
        "廉贞": (ziwei_pos - 8) % 12,
        "天府": tian_fu,
        "太阴": (tian_fu + 1) % 12,
        "贪狼": (tian_fu + 2) % 12,
        "巨门": (tian_fu + 3) % 12,
        "天相": (tian_fu + 4) % 12,
        "天梁": (tian_fu + 5) % 12,
        "七杀": (tian_fu + 6) % 12,
        "破军": (tian_fu + 10) % 12,
    }

# ===== 辅星 =====
# 天魁天钺：年干
TIANKUI = {
    "甲": (1, 7), "戊": (1, 7), "庚": (1, 7),  # 甲戊庚牛羊 -> 丑未
    "乙": (0, 8), "己": (0, 8),                # 乙己鼠猴乡 -> 子申
    "丙": (11, 9), "丁": (11, 9),              # 丙丁猪鸡位 -> 亥酉
    "壬": (3, 5), "癸": (3, 5),                # 壬癸兔蛇藏 -> 卯巳
    "辛": (6, 2),                              # 六辛逢马虎 -> 午寅
}
# 禄存：年干
LU_CUN = {"甲": 2, "乙": 3, "丙": 5, "丁": 6, "戊": 5, "己": 6, "庚": 8, "辛": 9, "壬": 11, "癸": 0}
# 火星铃星：年支三合局
HUO_LING = {
    "寅": (1, 3), "午": (1, 3), "戌": (1, 3),       # 寅午戌：火星丑、铃星卯（修正：火星随寅午戌入丑宫）
    "申": (2, 10), "子": (2, 10), "辰": (2, 10),   # 申子辰：火星寅、铃星戌
    "巳": (3, 10), "酉": (3, 10), "丑": (3, 10),   # 巳酉丑：火星卯、铃星戌
    "亥": (9, 10), "卯": (9, 10), "未": (9, 10),   # 亥卯未：火星酉、铃星戌
}

# ===== 四化（生年天干）=====
SIHUA = {
    "甲": {"禄": "廉贞", "权": "破军", "科": "武曲", "忌": "太阳"},
    "乙": {"禄": "天机", "权": "天梁", "科": "紫微", "忌": "太阴"},
    "丙": {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
    "丁": {"禄": "太阴", "权": "天同", "科": "天机", "忌": "巨门"},
    "戊": {"禄": "贪狼", "权": "太阴", "科": "右弼", "忌": "天机"},
    "己": {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"},
    "庚": {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"},
    "辛": {"禄": "巨门", "权": "太阳", "科": "文曲", "忌": "文昌"},
    "壬": {"禄": "天梁", "权": "紫微", "科": "左辅", "忌": "武曲"},
    "癸": {"禄": "破军", "权": "巨门", "科": "太阴", "忌": "贪狼"},
}

# 主星 -> 简短意象（sub 用）
STAR_MEANING = {
    "紫微": "帝座至尊", "天机": "智谋善变", "太阳": "光明博施", "武曲": "财星刚毅", "天同": "福星安逸",
    "廉贞": "次桃花·囚星", "天府": "财库稳重", "太阴": "田宅主·温柔", "贪狼": "欲望桃花", "巨门": "口才是非",
    "天相": "印星辅佐", "天梁": "荫星清高", "七杀": "将星冲劲", "破军": "耗星破旧立新",
    "左辅": "助力", "右弼": "助力", "文昌": "文星", "文曲": "才艺", "天魁": "贵人", "天钺": "贵人",
    "禄存": "财禄", "擎羊": "刑冲", "陀罗": "暗耗", "火星": "突发", "铃星": "阴火", "地空": "空亡",     "地劫": "劫耗",
}

# ===== 十四主星：北斗 6 / 南斗 8（主角：定每宫基本性格与气质）=====
MAIN14 = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞",
          "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"]
MAIN_STAR_CHAR = {
    # 北斗星系（6）
    "紫微": "帝座星，尊贵稳重、领导欲强，有统御气度但易显孤高。",
    "天机": "谋略星，聪慧机敏、善策划变通，宜参谋幕僚、以智取胜。",
    "太阳": "贵星，光明磊落、热心公益，喜抛头露面、得人景仰。",
    "武曲": "财星，刚毅果决、重信守诺，善理财与执行。",
    "天同": "福星，温和知足、随遇而安，贵人运佳、少劳多成。",
    "廉贞": "次桃花，才艺与是非并存，爱憎分明、重情而纠结。",
    # 南斗星系（8）
    "天府": "财库星，厚实稳重、善守成理财，格局从容不迫。",
    "太阴": "田宅星，温柔细腻、内敛多思，重家庭与审美。",
    "贪狼": "桃花星，多才多艺、交际手腕强，欲望机遇并存。",
    "巨门": "暗星，口才犀利、思辨深刻，宜以口为业，须防口舌。",
    "天相": "印星，斯文有礼、协调力强，掌印信文书、宜辅佐。",
    "天梁": "荫星，清高正直、有长辈缘，宜公职咨询、化解灾厄。",
    "七杀": "将星，冲劲果敢、敢作敢当，宜开创武职、不惧变动。",
    "破军": "耗星，破旧立新、不喜安稳，变动中求突破与发展。",
}
MAIN_GROUP = {s: ("北斗" if s in ("紫微", "天机", "太阳", "武曲", "天同", "廉贞") else "南斗") for s in MAIN14}

# ===== 辅星分类（配角：加减成色、补细节）=====
AUX_CAT = {
    # 六吉：左辅右弼文昌文曲天魁天钺
    "左辅": "吉", "右弼": "吉", "文昌": "吉", "文曲": "吉", "天魁": "吉", "天钺": "吉",
    # 六煞：擎羊陀罗火星铃星地空地劫
    "擎羊": "煞", "陀罗": "煞", "火星": "煞", "铃星": "煞", "地空": "煞", "地劫": "煞",
    # 禄存·天马
    "禄存": "财", "天马": "财",
    # 桃花杂曜
    "红鸾": "桃", "天喜": "桃", "咸池": "桃", "天姚": "桃",
}
AUX_CAT_LABEL = {"吉": "六吉", "煞": "六煞", "财": "禄存·天马", "桃": "桃花杂曜"}

# ===== 庙旺利陷（读法：判断星曜强弱）===== 评级：庙>旺>利>平>陷
MIAO_WANG = {
    "紫微": dict(zip(ZHI_ORDER, ["庙", "旺", "旺", "平", "旺", "平", "庙", "旺", "旺", "平", "旺", "平"])),
    "天机": dict(zip(ZHI_ORDER, ["庙", "平", "旺", "平", "陷", "旺", "平", "旺", "庙", "平", "陷", "旺"])),
    "太阳": dict(zip(ZHI_ORDER, ["陷", "平", "旺", "庙", "平", "旺", "庙", "平", "平", "旺", "陷", "平"])),
    "武曲": dict(zip(ZHI_ORDER, ["平", "庙", "平", "陷", "旺", "平", "旺", "平", "旺", "庙", "平", "陷"])),
    "天同": dict(zip(ZHI_ORDER, ["庙", "平", "平", "陷", "平", "旺", "庙", "平", "平", "旺", "平", "陷"])),
    "廉贞": dict(zip(ZHI_ORDER, ["平", "旺", "平", "陷", "旺", "庙", "平", "旺", "平", "陷", "旺", "庙"])),
    "天府": dict(zip(ZHI_ORDER, ["庙", "庙", "平", "旺", "陷", "旺", "平", "旺", "平", "庙", "陷", "旺"])),
    "太阴": dict(zip(ZHI_ORDER, ["庙", "旺", "平", "陷", "平", "平", "庙", "旺", "平", "旺", "陷", "平"])),
    "贪狼": dict(zip(ZHI_ORDER, ["庙", "旺", "平", "陷", "平", "平", "庙", "旺", "平", "旺", "陷", "平"])),
    "巨门": dict(zip(ZHI_ORDER, ["旺", "平", "旺", "陷", "平", "旺", "陷", "平", "旺", "平", "陷", "旺"])),
    "天相": dict(zip(ZHI_ORDER, ["平", "旺", "平", "陷", "旺", "平", "旺", "平", "旺", "平", "陷", "旺"])),
    "天梁": dict(zip(ZHI_ORDER, ["旺", "平", "旺", "陷", "平", "旺", "陷", "平", "旺", "平", "陷", "旺"])),
    "七杀": dict(zip(ZHI_ORDER, ["庙", "平", "平", "旺", "陷", "旺", "旺", "平", "旺", "庙", "陷", "平"])),
    "破军": dict(zip(ZHI_ORDER, ["庙", "平", "旺", "陷", "平", "旺", "旺", "平", "平", "旺", "陷", "平"])),
}

# ===== 天马 / 桃花杂曜 安星 =====
TIANMA = {  # 年支 -> 宫位(0-11)
    "寅": 8, "午": 8, "戌": 8, "申": 2, "子": 2, "辰": 2,
    "巳": 9, "酉": 9, "丑": 9, "亥": 3, "卯": 3, "未": 3,
}
HONGLUAN = {z: (3 - i) % 12 for i, z in enumerate(ZHI_ORDER)}      # 红鸾
TIANXI = {z: (HONGLUAN[z] + 6) % 12 for z in ZHI_ORDER}            # 天喜（红鸾对宫）
XIANCHI = {  # 咸池（桃花）
    "寅": 3, "午": 3, "戌": 3, "申": 9, "子": 9, "辰": 9,
    "巳": 6, "酉": 6, "丑": 6, "亥": 0, "卯": 0, "未": 0,
}
TIANYAO = {z: (1 + i) % 12 for i, z in enumerate(["丑", "卯", "巳", "未", "酉", "亥", "子", "寅", "辰", "午", "申", "戌"])}

# ===== 大限（时间：阶段重心）=====
def _dafen(gender: str, year_gan: str, ming_palace: int, star_positions: dict, ju: int) -> list:
    """返回 12 个大限：[{age, palace, star, dir}]。"""
    yang = year_gan in ("甲", "丙", "戊", "庚", "壬")
    forward = (yang and gender == "男") or ((not yang) and gender == "女")
    pos_to_star = {p: s for s, p in star_positions.items()}
    dafen = []
    cur = 0  # 命宫 palace index
    for k in range(12):
        age_start = ju + k * 10
        pzhi = (ming_palace - cur) % 12
        star = pos_to_star.get(pzhi, "")
        dafen.append({
            "age": f"{age_start}-{age_start + 9}岁",
            "palace": PALACE_NAMES[cur],
            "star": star,
            "dir": "顺" if forward else "逆",
        })
        cur = (cur - 1) % 12 if forward else (cur + 1) % 12
    return dafen

# ===== 三方四正（读法：联动）=====
def _sifang(ming_palace: int, palace_zhi: int) -> list:
    """本宫 + 三合 + 对宫 的宫名列表。"""
    idxs = [palace_zhi, (palace_zhi + 4) % 12, (palace_zhi + 8) % 12, (palace_zhi + 6) % 12]
    return [PALACE_NAMES[(ming_palace - z) % 12] for z in idxs]

# ===== 命格特质（命宫主星组合）=====
def _traits_text(ming_stars: list[str]) -> tuple[list[dict], str]:
    """根据命宫主星生成命格特质与解读文字。"""
    stars = [s for s in ming_stars if s in ("紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府",
                                            "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军")]
    traits = []
    analysis_parts = []
    if not stars:
        traits = [
            {"icon": "🌊", "name": "适应力", "stars": "⭐⭐⭐⭐", "color": "var(--accent-cyan)"},
            {"icon": "🧠", "name": "借宫思维", "stars": "⭐⭐⭐⭐", "color": "var(--primary-light)"},
            {"icon": "🤝", "name": "贵人缘", "stars": "⭐⭐⭐", "color": "var(--accent-pink)"},
        ]
        analysis_parts.append("命宫为空宫，借对宫星系入命，性格弹性大、适应力强，易受环境与贵人影响。")
    else:
        first = stars[0]
        desc = {
            "紫微": ("👑", "领导力", "⭐⭐⭐⭐⭐", "var(--accent-gold)", "紫微坐命为「帝座格」，天生领袖气质，喜掌权、重体面，格局宏大。"),
            "天机": ("💡", "智慧", "⭐⭐⭐⭐⭐", "var(--primary-light)", "天机坐命为「智谋格」，头脑灵活、反应机敏，善策划与应变。"),
            "太阳": ("☀️", "光明磊落", "⭐⭐⭐⭐", "var(--accent-gold)", "太阳坐命，光明磊落、热心助人，适合公众表达与公益事业。"),
            "武曲": ("💰", "执行力", "⭐⭐⭐⭐⭐", "var(--accent-green)", "武曲坐命为「财星格」，刚毅果决、执行力强，理财能力突出。"),
            "天同": ("🎈", "福气", "⭐⭐⭐⭐", "var(--accent-cyan)", "天同坐命为「福星格」，性情温和、知足常乐，贵人运佳。"),
            "廉贞": ("🔥", "才华", "⭐⭐⭐⭐", "var(--accent-pink)", "廉贞坐命为「次桃花」，才艺出众、爱憎分明，人缘与是非并存。"),
            "天府": ("🏛️", "稳重", "⭐⭐⭐⭐⭐", "var(--accent-green)", "天府坐命为「财库格」，稳重厚实、善于理财守成。"),
            "太阴": ("🌙", "细腻", "⭐⭐⭐⭐", "#a78bfa", "太阴坐命，温柔细腻、心思缜密，审美与照顾能力俱佳。"),
            "贪狼": ("🌸", "魅力", "⭐⭐⭐⭐", "var(--accent-pink)", "贪狼坐命为「桃花格」，多才多艺、交际手腕强，欲望与机遇并存。"),
            "巨门": ("🎙️", "口才", "⭐⭐⭐⭐", "var(--accent-cyan)", "巨门坐命，口才犀利、思辨力强，宜以口为业，需防口舌。"),
            "天相": ("📜", "协调", "⭐⭐⭐⭐", "var(--accent-gold)", "天相坐命为「印星格」，斯文有礼、协调力强，适合辅助与幕僚。"),
            "天梁": ("🛡️", "荫庇", "⭐⭐⭐⭐", "var(--accent-green)", "天梁坐命为「荫星格」，正直清高、有长辈缘，宜公职与咨询。"),
            "七杀": ("⚔️", "魄力", "⭐⭐⭐⭐⭐", "#ff6b6b", "七杀坐命为「将星格」，冲劲十足、敢作敢当，宜武职与开创。"),
            "破军": ("🔄", "突破", "⭐⭐⭐⭐", "#ff8e53", "破军坐命为「破耗格」，破旧立新、不喜安稳，变动中求发展。"),
        }
        if first in desc:
            icon, name, n, color, text = desc[first]
            traits.append({"icon": icon, "name": name, "stars": n, "color": color})
            analysis_parts.append(text)
        if len(stars) >= 2:
            second = stars[1]
            combo = {
                "紫微": "紫微坐命喜得左辅右弼/禄存夹，帝王之气，统御八方。",
                "天府": "府库同宫，财权双美，格局更上层楼。",
                "天相": "紫微天相，辅弼之星，宜掌印信、文书之权。",
                "七杀": "紫微七杀化杀为权，魄力与格局并重，宜开创大业。",
                "破军": "紫微破军，先破后立，变动中见机遇。",
                "贪狼": "贪狼会禄，桃花化财，社交变现能力极强。",
                "太阳": "太阳在命，光芒外放，人前显贵。",
            }
            for k, v in combo.items():
                if k in stars and k != first:
                    analysis_parts.append(v)
                    break
    # 补齐 4 项特质
    extras = [
        {"icon": "💕", "name": "人缘", "stars": "⭐⭐⭐⭐", "color": "var(--accent-pink)"},
        {"icon": "💪", "name": "抗压", "stars": "⭐⭐⭐", "color": "var(--accent-green)"},
    ]
    for e in extras:
        if len(traits) < 4:
            traits.append(e)
    return traits[:4], " ".join(analysis_parts)


def _liunian_for(target_year: int, birth_zhi_idx: int, ming_palace: int,
                 pos_to_star: dict) -> dict:
    """计算指定公历年份的流年命盘（流年命宫 / 太岁宫 / 落宫主星）。

    流年命宫 = (出生年地支序 - 流年地支序) 顺逆推演，公式与命宫安法同构。
    """
    t_zhi_idx = (target_year - 4) % 12
    steps = (t_zhi_idx - birth_zhi_idx) % 12
    ming_idx = (0 - steps) % 12
    tai_idx = (ming_palace - t_zhi_idx) % 12
    star = pos_to_star.get((ming_palace - ming_idx) % 12, "")
    return {
        "year": target_year,
        "zhi": ZHI_ORDER[t_zhi_idx],
        "mingPalace": PALACE_NAMES[ming_idx],
        "taiPalace": PALACE_NAMES[tai_idx],
        "star": star,
    }


def _liuyue_list(target_year: int, birth_zhi_idx: int, ming_palace: int,
                pos_to_star: dict) -> list:
    """计算指定公历年份的 12 个流月命宫（农历正月~腊月）。"""
    t_zhi_idx = (target_year - 4) % 12
    steps = (t_zhi_idx - birth_zhi_idx) % 12
    ming_idx = (0 - steps) % 12
    out = []
    for m in range(1, 13):
        idx = (ming_idx - (m - 1)) % 12
        star = pos_to_star.get((ming_palace - idx) % 12, "")
        out.append({"month": m, "mingPalace": PALACE_NAMES[idx], "star": star})
    return out


# ============================================================================
# 增补模块：杂曜 / 长生十二神 / 宫干四化(飞星) / 小限 / 流年四化 / 格局识别 / 空宫借星
# ============================================================================

# ----- 杂曜（年支/年干三合局安法，标准口径） -----
GU_CHEN = {"寅": 5, "午": 5, "戌": 5, "申": 2, "子": 2, "辰": 2, "巳": 8, "酉": 8, "丑": 8, "亥": 11, "卯": 11, "未": 11}  # 孤辰
GUA_SU = {"寅": 4, "午": 4, "戌": 4, "申": 1, "子": 1, "辰": 1, "巳": 11, "酉": 11, "丑": 11, "亥": 10, "卯": 10, "未": 10}  # 寡宿
HUA_GAI = {"寅": 10, "午": 10, "戌": 10, "申": 4, "子": 4, "辰": 4, "巳": 1, "酉": 1, "丑": 1, "亥": 7, "卯": 7, "未": 7}  # 华盖
PO_SUI = {"寅": 9, "午": 9, "戌": 9, "申": 5, "子": 5, "辰": 5, "巳": 1, "酉": 1, "丑": 1, "亥": 7, "卯": 7, "未": 7}  # 破碎
TIAN_XING = {"寅": 1, "午": 1, "戌": 1, "申": 2, "子": 2, "辰": 2, "巳": 3, "酉": 3, "丑": 3, "亥": 9, "卯": 9, "未": 9}  # 天刑

# ===== 本命杂曜（口径确定者；其余高分歧杂曜见待校验清单，留待权威盘 cross-check） =====
# 天巫：年干禄宫前一位（甲禄寅->卯，乙禄卯->辰…）— 解厄类杂曜
TIAN_WU = {"甲": 3, "乙": 4, "丙": 6, "丁": 7, "戊": 6, "己": 7, "庚": 9, "辛": 10, "壬": 0, "癸": 1}
# 天厨：年干食神之禄宫（甲食神丙、丙禄巳；乙食神丁、丁禄午…）— 福禄/才艺
_TIAN_CHU_LU = {"甲": 5, "乙": 6, "丙": 5, "丁": 6, "戊": 8, "己": 9, "庚": 11, "辛": 0, "壬": 2, "癸": 3}
TIAN_CHU = _TIAN_CHU_LU
# 月德：生月三合局阳干所临禄宫（寅午戌->丙->巳；申子辰->壬->亥；亥卯未->甲->寅；巳酉丑->庚->申）
YUE_DE = {0: 11, 4: 11, 8: 11, 2: 5, 6: 5, 10: 5, 11: 2, 3: 2, 7: 2, 5: 8, 9: 8, 1: 8}
# 劫煞：年支三合局之绝地（寅午戌->亥；申子辰->巳；亥卯未->申；巳酉丑->寅）
JIE_SHA = {2: 11, 6: 11, 10: 11, 8: 5, 0: 5, 4: 5, 11: 8, 3: 8, 7: 8, 5: 2, 9: 2, 1: 2}
# 阴煞：年支三合局前一辰（寅午戌->寅；申子辰->戌；亥卯未->午；巳酉丑->辰）
YIN_SHA = {2: 2, 6: 2, 10: 2, 8: 10, 0: 10, 4: 10, 11: 6, 3: 6, 7: 6, 5: 4, 9: 4, 1: 4}


def _xunkong(gz_idx: int) -> list[int]:
    """年柱旬空（空亡）的两个地支序。"""
    s = gz_idx // 10  # 旬 0-5
    return [(10 - 2 * s) % 12, (11 - 2 * s) % 12]


JIE_KONG = {
    "甲": (8, 9), "己": (8, 9), "乙": (6, 7), "庚": (6, 7),
    "丙": (4, 5), "辛": (4, 5), "丁": (2, 3), "壬": (2, 3),
    "戊": (0, 1), "癸": (0, 1),
}

# ===== 高分歧杂曜（补全）=====
# 注意：以下杂曜各流派安星口径略有出入（尤其天德/天官/天福/天才天寿）。
# 本实现采用「常见排盘法」（与多数在线排盘/中州派常用诀一致），并锁定回归测试，
# 后续如需切换到其它流派，改这里 + 同步 tests/test_ziwei.py 即可。
# 天官（年干）：甲寅 乙卯 丙巳 丁午 戊巳 己午 庚申 辛酉 壬亥 癸子
TIAN_GUAN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
              "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
# 天福（年干）：甲酉 乙申 丙子 丁亥 戊子 己亥 庚卯 辛寅 壬午 癸巳
TIAN_FU = {"甲": "酉", "乙": "申", "丙": "子", "丁": "亥", "戊": "子",
            "己": "亥", "庚": "卯", "辛": "寅", "壬": "午", "癸": "巳"}
# 天德（月支 -> 地支）：寅午 卯申 辰亥 巳酉 午亥 未寅 申子 酉寅 戌巳 亥卯 子午 丑申
TIAN_DE = {2: "午", 3: "申", 4: "亥", 5: "酉", 6: "亥", 7: "寅",
            8: "子", 9: "寅", 10: "巳", 11: "卯", 0: "午", 1: "申"}
# 年支顺布类：子年落 base 宫，顺行每宫一宫（base 为绝对地支序）
LONG_CHI_BASE = ZHI_ORDER.index("辰")    # 龙池：子年辰
FENG_GE_BASE = ZHI_ORDER.index("戌")     # 凤阁：子年戌
TAI_FU_BASE = ZHI_ORDER.index("午")      # 台辅：子年午
FENG_GAO_BASE = ZHI_ORDER.index("寅")    # 封诰：子年寅
EN_GUANG_BASE = ZHI_ORDER.index("酉")    # 恩光：子年酉
TIAN_GUI_BASE = ZHI_ORDER.index("卯")    # 天贵：子年卯


# ----- 长生十二神 -----
CHANGSHENG_SEQ = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANGSHENG_START = {"水": 8, "木": 10, "金": 5, "火": 2, "土": 8}  # 局五行 -> 长生地支序（土寄水，同申）
JU_WUXING = {2: "水", 3: "木", 4: "金", 5: "土", 6: "火"}


def _changsheng_for(ju: int, gender: str, year_gan: str) -> dict[int, str]:
    """各宫(0-11)所落长生十二神。阳男阴女顺、阳女阴男逆。"""
    wx = JU_WUXING.get(ju, "水")
    start = CHANGSHENG_START[wx]
    yang = year_gan in ("甲", "丙", "戊", "庚", "壬")
    forward = (yang and gender == "男") or ((not yang) and gender == "女")
    return {
        i: CHANGSHENG_SEQ[(i - start) % 12 if forward else (start - i) % 12]
        for i in range(12)
    }


# ----- 宫干四化（飞星派核心） -----
def _palace_sihua(palace_gan: list[str], all_stars: dict[str, int]) -> list[dict]:
    """逐宫以本宫宫干飞化禄权科忌，落宫为该星在盘中所处宫位；同宫即自化。"""
    out: list[dict] = []
    for i, gan in enumerate(palace_gan):
        mp = PALACE_NAMES[i]
        for hua, star in SIHUA.get(gan, {}).items():
            to_pos = all_stars.get(star)
            if to_pos is None:
                continue
            out.append({
                "from": mp, "hua": hua, "star": star,
                "to": PALACE_NAMES[to_pos], "self": to_pos == i,
            })
    return out


# ----- 小限（年支 + 虚岁） -----
def _xiaoxian_zhi(birth_zhi_idx: int, virtual_age: int) -> int:
    """小限所在宫地支序：生年支起 1 岁顺数至虚岁。"""
    return (birth_zhi_idx + virtual_age - 1) % 12


# ----- 流年 / 流月四化（运四化） -----
def _year_gan_of(year: int) -> str:
    """目标公历年份的农历年干（以正月初一为界，简化口径）。"""
    return Solar.fromYmd(year, 1, 1).getLunar().getYearInGanZhi()[0]


def _month_gan_of(year_gan: str, lm: int) -> str:
    """农历月干（五虎遁）：年干 + 月序 -> 月干。"""
    return GAN_ORDER[(GAN_ORDER.index(year_gan) * 2 + 2 + (lm - 1)) % 10]


def _yun_sihua(year_gan: str, all_stars: dict[str, int]) -> list[dict]:
    """按某年/月天干飞四化，返回 [{'hua','star','palace'}]（落宫取本命盘星位）。"""
    out: list[dict] = []
    for hua, star in SIHUA.get(year_gan, {}).items():
        pos = all_stars.get(star)
        if pos is None:
            continue
        out.append({"hua": hua, "star": star, "palace": PALACE_NAMES[pos]})
    return out


# ----- 格局识别引擎（规则引擎） -----
def _detect_patterns(palace_stars: dict[str, set], ming_palace: int, year_gan: str) -> list[dict]:
    """基于十二宫星曜组合识别常见格局（命中即返回，供前端展示 + RAG 文案）。"""
    allset = set().union(*palace_stars.values()) if palace_stars else set()

    def star_palace(star: str) -> str | None:
        for p, s in palace_stars.items():
            if star in s:
                return p
        return None

    def related(p1: str | None, star: str) -> bool:
        """star 与 p1(宫名) 同宫或落其三方四正(含对宫)。"""
        if not p1:
            return star in allset
        pos = (ming_palace - PALACE_NAMES.index(p1)) % 12
        rel = {p1} | set(_sifang(ming_palace, pos))
        return any(star in palace_stars.get(p, set()) for p in rel)

    pats: list[dict] = []
    zg = star_palace("紫微")
    # 1 紫府同宫
    if zg and zg == star_palace("天府"):
        pats.append({"name": "紫府同宫格", "desc": "紫微天府同守一宫，帝相并临，贵显富足、领导力与财库兼得。"})
    # 2 君臣庆会
    if zg and all(related(zg, x) for x in ("左辅", "右弼", "文昌", "文曲")):
        pats.append({"name": "君臣庆会格", "desc": "紫微得左右昌曲朝拱，君主得良臣辅弼，贵人鼎盛、格局清正。"})
    # 3 机月同梁
    if all(s in allset for s in ("天机", "太阴", "天同", "天梁")):
        pats.append({"name": "机月同梁格", "desc": "善荫谋略之格，主文职清贵、计划周密，利政教幕僚。"})
    # 4 杀破狼
    if any(related(star_palace("命宫"), s) for s in ("七杀", "破军", "贪狼")):
        pats.append({"name": "杀破狼格", "desc": "七杀破军贪狼会照，变动开创之格，人生起伏大、敢闯敢破。"})
    # 5 巨日同宫/对照
    if star_palace("太阳") and related(star_palace("太阳"), "巨门"):
        pats.append({"name": "巨日同宫格", "desc": "太阳巨门同宫或对照，明察善辩、以才显达，庙旺利专业表达。"})
    # 6 日月并明
    if "太阳" in allset and "太阴" in allset:
        pats.append({"name": "日月并明格", "desc": "太阳太阴交辉，主声名清贵、内外兼修、明暗得宜。"})
    # 7 火贪 / 铃贪
    if star_palace("火星") and related(star_palace("火星"), "贪狼"):
        pats.append({"name": "火贪格", "desc": "火星贪狼同宫或对照，火贪相聚主突发暴发，宜把握机遇。"})
    if star_palace("铃星") and related(star_palace("铃星"), "贪狼"):
        pats.append({"name": "铃贪格", "desc": "铃星贪狼同宫或对照，主暗中崛起、以韧致成。"})
    # 8 文桂文华
    if star_palace("文昌") and related(star_palace("文昌"), "文曲"):
        pats.append({"name": "文桂文华格", "desc": "文昌文曲同宫或对照，才情出众、文采风流，利艺文学术。"})
    # 9 双禄朝垣（禄存与会生年化禄之星拱照）
    lua = SIHUA.get(year_gan, {}).get("禄")
    if lua and "禄存" in allset and star_palace("禄存") and related(star_palace("禄存"), lua):
        pats.append({"name": "双禄朝垣格", "desc": "禄存与会生年化禄之星拱照，双禄并临，财源丰沛、安稳积聚。"})
    # 10 三奇嘉会（化禄权科三奇会照命宫）
    sh = SIHUA.get(year_gan, {})
    sanqi = [sh.get("禄"), sh.get("权"), sh.get("科")]
    if all(sanqi) and star_palace("命宫") and all(related(star_palace("命宫"), s) for s in sanqi):
        pats.append({"name": "三奇嘉会格", "desc": "化禄权科三奇会照命宫，主贵显荣达、机遇与才华并济。"})
    # 11 马头带箭
    for p, s in palace_stars.items():
        if {"天马", "七杀", "擎羊"} <= s:
            pats.append({"name": "马头带箭格", "desc": "天马七杀擎羊同宫，威震边庭之格，主武职开创、果敢决断。"})
            break
    # 12 明珠出海（太阴居水宫亥子丑庙旺）
    for p, s in palace_stars.items():
        if "太阴" in s and p in ("子女", "财帛", "田宅", "迁移"):
            pats.append({"name": "明珠出海格", "desc": "太阴居水宫庙旺，明珠出海，主内秀得财、荫福绵长。"})
            break
    # 13 阳梁昌禄
    if all(s in allset for s in ("太阳", "天梁", "文昌", "禄存")):
        pats.append({"name": "阳梁昌禄格", "desc": "太阳天梁逢文昌禄存，主功名显达、以才得禄。"})
    return pats


def compute_ziwei(year: int, month: int, day: int, hour: int | None = None,
                  gender: str = "男", time_text: str = "",
                  target_year: int | None = None, target_month: int | None = None) -> dict:
    """紫微斗数排盘。hour: 0-23；None 为时辰不详（用午时补排）。"""
    h = hour if hour is not None else 12
    if time_text and hour is None:
        h = _time_to_hour(time_text)

    solar = Solar.fromYmdHms(year, month, day, h, 0, 0)
    lunar = solar.getLunar()
    lm = lunar.getMonth()
    ld = lunar.getDay()
    if lm < 0:
        lm = -lm  # 闰月按该月处理（简化口径）
    hour_zhi_idx = (h + 1) // 2 % 12  # 0=子 1=丑 ...

    year_gan = lunar.getYearInGanZhi()[0]
    year_zhi = lunar.getYearInGanZhi()[1]

    # 1. 命宫 / 身宫（寅宫起正月顺数；命逆身顺）
    yin = 2
    month_palace = (yin + (lm - 1)) % 12
    ming_palace = (month_palace - hour_zhi_idx) % 12
    shen_palace = (month_palace + hour_zhi_idx) % 12

    # 2. 五虎遁定宫干：寅宫起正月干（年干遁出正月干），顺布十二宫（下标=宫位 0子..11亥）
    yin_gan_idx = (GAN_ORDER.index(year_gan) * 2 + 2) % 10  # 寅宫(正月)宫干
    palace_gan = [GAN_ORDER[(yin_gan_idx + ((i - 2) % 12)) % 10] for i in range(12)]

    # 3. 五行局（命宫干支纳音）
    ming_gan = palace_gan[ming_palace]
    ming_zhi = ZHI_ORDER[ming_palace]
    gz_i = _gz_index(ming_gan, ming_zhi)
    nayin = _nayin(gz_i)
    ju = JU_BY_NAYIN[nayin[-1]]

    # 4. 紫微定位
    ziwei_pos = (JU_START[ju] - (ld - 1)) % 12

    # 5. 十四主星
    star_positions = _zhu_star_positions(ziwei_pos)

    # 6. 辅星
    tiankui, tianyue = TIANKUI.get(year_gan, (None, None))
    lu_cun = LU_CUN.get(year_gan)
    huol, ling = HUO_LING.get(year_zhi, (None, None))
    fu = {
        "左辅": (4 + (lm - 1)) % 12,
        "右弼": (10 - (lm - 1)) % 12,
        "文昌": (10 + hour_zhi_idx) % 12,
        "文曲": (4 - hour_zhi_idx) % 12,
        "禄存": lu_cun,
        "擎羊": (lu_cun + 1) % 12 if lu_cun is not None else None,
        "陀罗": (lu_cun - 1) % 12 if lu_cun is not None else None,
        "火星": huol,
        "铃星": ling,
        "地空": (11 + hour_zhi_idx) % 12,
        "地劫": (11 - hour_zhi_idx) % 12,
        "天魁": tiankui,
        "天钺": tianyue,
        "天马": TIANMA.get(year_zhi),
        "红鸾": HONGLUAN.get(year_zhi),
        "天喜": TIANXI.get(year_zhi),
        "咸池": XIANCHI.get(year_zhi),
        "天姚": TIANYAO.get(year_zhi),
    }

    # 7. 十二宫
    palaces = []
    all_stars = dict(star_positions)
    for name, pos in fu.items():
        if pos is not None:
            all_stars[name] = pos
    pos_to_star = {p: s for s, p in all_stars.items()}
    for i, name in enumerate(PALACE_NAMES):
        pos = (ming_palace - i) % 12
        stars_in = [s for s, p in all_stars.items() if p == pos]
        main = [s for s in stars_in if s in MAIN14]
        sub = [s for s in stars_in if s not in MAIN14]
        star_text = "+".join(main) if main else "—"
        sub_text = "+".join(sub) if sub else ""
        meanings = [STAR_MEANING.get(s, "") for s in main]
        # 主角气质 + 庙旺利陷
        main_desc = ""
        bright = ""
        if main:
            ms = main[0]
            main_desc = MAIN_STAR_CHAR.get(ms, "")
            bright = MIAO_WANG.get(ms, {}).get(ZHI_ORDER[pos], "")
        # 配角分组（六吉/六煞/禄存天马/桃花杂曜）
        aux = {"吉": [], "煞": [], "财": [], "桃": []}
        for s in sub:
            cat = AUX_CAT.get(s)
            if cat:
                aux[cat].append(s)
        # 三方四正
        sifang = _sifang(ming_palace, pos)
        palaces.append({
            "name": name,
            "icon": PALACE_ICONS[name],
            "color": PALACE_COLORS[name],
            "star": star_text,
            "sub": sub_text or (meanings[0] if meanings else "无主星"),
            "pos": ZHI_ORDER[pos],
            "gan": palace_gan[pos],
            "highlight": name == "命宫",
            "isShenGong": pos == shen_palace,
            "mainDesc": main_desc,
            "bright": bright,
            "aux": aux,
            "sifang": sifang,
        })

    # 7b. 增补：杂曜 / 长生十二神 / 空宫借星（写入各宫 dict）
    year_gz_idx = _gz_index(year_gan, year_zhi)
    misc_map: dict[str, list[str]] = {}
    def _add_misc(name: str, zhi_idx: int) -> None:
        pidx = (ming_palace - zhi_idx) % 12
        misc_map.setdefault(PALACE_NAMES[pidx], []).append(name)
    if year_zhi in GU_CHEN:
        _add_misc("孤辰", GU_CHEN[year_zhi])
    if year_zhi in GUA_SU:
        _add_misc("寡宿", GUA_SU[year_zhi])
    if year_zhi in HUA_GAI:
        _add_misc("华盖", HUA_GAI[year_zhi])
    if year_zhi in PO_SUI:
        _add_misc("破碎", PO_SUI[year_zhi])
    if year_zhi in TIAN_XING:
        _add_misc("天刑", TIAN_XING[year_zhi])
    # 本命杂曜（口径确定者）：年干/年支/生月固定公式
    if year_gan in TIAN_WU:
        _add_misc("天巫", TIAN_WU[year_gan])
    if year_gan in TIAN_CHU:
        _add_misc("天厨", TIAN_CHU[year_gan])
    month_zhi_idx = (lm + 1) % 12
    yd = YUE_DE.get(month_zhi_idx)
    if yd is not None:
        _add_misc("月德", yd)
    yzi = ZHI_ORDER.index(year_zhi)
    if yzi in JIE_SHA:
        _add_misc("劫煞", JIE_SHA[yzi])
    if yzi in YIN_SHA:
        _add_misc("阴煞", YIN_SHA[yzi])
    for z in _xunkong(year_gz_idx):
        _add_misc("旬空", z)
    for z in JIE_KONG.get(year_gan, ()):
        _add_misc("截空", z)
    # 高分歧杂曜补全（年干/年支/月支/宫位派生；常见排盘法，已锁定回归）
    if year_gan in TIAN_GUAN:
        _add_misc("天官", ZHI_ORDER.index(TIAN_GUAN[year_gan]))
    if year_gan in TIAN_FU:
        _add_misc("天福", ZHI_ORDER.index(TIAN_FU[year_gan]))
    if month_zhi_idx in TIAN_DE:
        _add_misc("天德", ZHI_ORDER.index(TIAN_DE[month_zhi_idx]))
    _add_misc("龙池", (LONG_CHI_BASE + yzi) % 12)
    _add_misc("凤阁", (FENG_GE_BASE + yzi) % 12)
    _add_misc("台辅", (TAI_FU_BASE + yzi) % 12)
    _add_misc("封诰", (FENG_GAO_BASE + yzi) % 12)
    _add_misc("恩光", (EN_GUANG_BASE + yzi) % 12)
    _add_misc("天贵", (TIAN_GUI_BASE + yzi) % 12)
    # 三台随左辅、八座随右弼（同宫）
    zuofu_p = (4 + (lm - 1)) % 12
    youbi_p = (10 - (lm - 1)) % 12
    _add_misc("三台", zuofu_p)
    _add_misc("八座", youbi_p)
    # 天才在命宫、天寿在身宫
    _add_misc("天才", ming_palace)
    _add_misc("天寿", shen_palace)
    # 天哭天虚：年支对宫（六冲）
    kx = (yzi + 6) % 12
    _add_misc("天哭", kx)
    _add_misc("天虚", kx)
    # 长生十二神
    changsheng_map = _changsheng_for(ju, gender, year_gan)
    for p in palaces:
        pidx = PALACE_NAMES.index(p["name"])
        pzhi = (ming_palace - pidx) % 12
        p["misc"] = misc_map.get(p["name"], [])
        p["changsheng"] = changsheng_map.get(pzhi, "")
        # 空宫借星：本宫无主星则借对宫主星
        if p["star"] in ("—", ""):
            opp_name = PALACE_NAMES[(pidx + 6) % 12]
            opp = next((x for x in palaces if x["name"] == opp_name), None)
            borrow = opp["star"].split("+") if (opp and opp["star"] not in ("—", "")) else []
            p["borrow"] = borrow
        else:
            p["borrow"] = []

    # 7c. 宫星总表（主星+辅星+杂曜），供格局识别与飞化
    palace_stars_map: dict[str, set] = {}
    for p in palaces:
        names: set = set()
        if p["star"] not in ("—", ""):
            names.update(p["star"].split("+"))
        if p.get("sub") and p["sub"] != "无主星":
            names.update(x for x in p["sub"].split("+") if x)
        for cat in p.get("aux", {}).values():
            names.update(cat)
        names.update(p.get("misc", []))
        palace_stars_map[p["name"]] = names

    # 8. 宫干四化（飞星派核心）
    palace_sihua = _palace_sihua(palace_gan, all_stars)

    # 9. 格局识别引擎
    patterns = _detect_patterns(palace_stars_map, ming_palace, year_gan)

    # 10. 四化（生年四化）
    sihua = []
    for hua_name, star in SIHUA.get(year_gan, {}).items():
        pos = all_stars.get(star)
        if pos is not None:
            palace_name = PALACE_NAMES[(ming_palace - pos) % 12]
            sihua.append({"star": star, "hua": hua_name, "palace": palace_name})

    # 9. 命格特质
    ming_pos = (ming_palace) % 12
    ming_stars = [s for s, p in all_stars.items() if p == ming_pos]
    traits, analysis = _traits_text(ming_stars)

    # 10. 大限 / 流年 / 流月（时间：应期与阶段重心）
    dafen = _dafen(gender, year_gan, ming_palace, star_positions, ju)
    now = datetime.datetime.now()
    birth_zhi_idx = ZHI_ORDER.index(year_zhi)
    # 指定年份/月份查询（P0：流年/流月可切换）；未指定则取当前
    eff_year = target_year if target_year else now.year
    liuNian = _liunian_for(eff_year, birth_zhi_idx, ming_palace, pos_to_star)
    t_zhi_idx = (eff_year - 4) % 12
    steps = (t_zhi_idx - birth_zhi_idx) % 12
    liu_nian_ming_idx = (0 - steps) % 12
    # 当前农历月（流月基准）；指定月份则直接采用
    if target_month is not None:
        cur_lm = target_month
    else:
        solar_now = Solar.fromYmdHms(now.year, now.month, now.day, 12, 0, 0)
        cur_lm = solar_now.getLunar().getMonth()
        if cur_lm < 0:
            cur_lm = -cur_lm
    liu_yue_ming_idx = (liu_nian_ming_idx - (cur_lm - 1)) % 12
    liuYue = {
        "month": cur_lm,
        "mingPalace": PALACE_NAMES[liu_yue_ming_idx],
        "star": pos_to_star.get((ming_palace - liu_yue_ming_idx) % 12, ""),
    }
    # 可浏览范围：以查询年份为中心前后若干年（前端做年份选择器，无需二次请求）
    YEAR_LO, YEAR_HI = eff_year - 2, eff_year + 16
    liuNianRange = [_liunian_for(y, birth_zhi_idx, ming_palace, pos_to_star) for y in range(YEAR_LO, YEAR_HI + 1)]
    liuYueByYear = {y: _liuyue_list(y, birth_zhi_idx, ming_palace, pos_to_star) for y in range(YEAR_LO, YEAR_HI + 1)}

    # 10b. 小限（年支 + 虚岁）
    virtual_age = max(1, eff_year - year + 1)  # 虚岁 ≈ 当年 - 出生年 + 1
    xiao_zhi = _xiaoxian_zhi(birth_zhi_idx, virtual_age)
    xiaoXian = {
        "age": f"{virtual_age}岁(虚)",
        "palace": PALACE_NAMES[(ming_palace - xiao_zhi) % 12],
        "zhi": ZHI_ORDER[xiao_zhi],
    }

    # 10c. 流年 / 流月四化（运四化）：按流年/月天干飞禄权科忌
    liuNianSihua = _yun_sihua(_year_gan_of(eff_year), all_stars)
    liuNianSihuaRange = {
        y: _yun_sihua(_year_gan_of(y), all_stars) for y in range(YEAR_LO, YEAR_HI + 1)
    }
    liuYueSihuaByYear = {
        y: {m: _yun_sihua(_month_gan_of(_year_gan_of(y), m), all_stars) for m in range(1, 13)}
        for y in range(YEAR_LO, YEAR_HI + 1)
    }
    liuYueSihua = liuYueSihuaByYear.get(eff_year, {}).get(cur_lm, [])

    # 10d. 流年十二宫盘（以流年命宫为基准重排十二宫，叠加太岁标注）
    # 流年盘 = 同一命盘的"换命宫基准"视角：流年命宫落原盘某宫，十二宫自该宫逆布。
    liu_nian_ming_zhi_idx = (ming_palace - liu_nian_ming_idx) % 12  # 流年命宫的地支序
    liuNianPan = []
    for i, name in enumerate(PALACE_NAMES):
        zhi_idx = (liu_nian_ming_zhi_idx - i) % 12  # 流年盘第 i 宫（命宫起逆）的地支序
        zhi = ZHI_ORDER[zhi_idx]
        src = next((p for p in palaces if p["pos"] == zhi), None)
        liuNianPan.append({
            "name": name,
            "pos": zhi,
            "star": src["star"] if src else "—",
            "sub": (src["sub"] if (src and src["sub"] != "无主星") else ""),
            "isMingGong": i == 0,           # 流年命宫
            "taiSui": zhi_idx == t_zhi_idx,  # 太岁（流年地支）标注
        })

    # 11. 十四主星参考（主角：北斗 6 / 南斗 8）
    mainStarsRef = [{"name": s, "group": MAIN_GROUP[s], "char": MAIN_STAR_CHAR[s]} for s in MAIN14]

    return {
        "solar": f"{year:04d}-{month:02d}-{day:02d}",
        "lunar": lunar.toString(),
        "timeText": time_text or ("不详" if hour is None else f"{h}时"),
        "mingGong": f"{ming_gan}{ming_zhi}宫（{ZHI_ORDER[ming_palace]}）",
        "shenGong": f"{ZHI_ORDER[shen_palace]}宫",
        "shenGongName": PALACE_NAMES[(ming_palace - shen_palace) % 12],
        "wuxingJu": f"{nayin} · {ju}局",
        "ziwei": f"紫微在{ZHI_ORDER[ziwei_pos]}",
        "palaces": palaces,
        "sihua": sihua,
        "traits": traits,
        "analysis": analysis,
        "mainStarsRef": mainStarsRef,
        "dafen": dafen,
        "liuNian": liuNian,
        "liuYue": liuYue,
        "liuNianRange": liuNianRange,
        "liuYueByYear": liuYueByYear,
        "patterns": patterns,
        "palaceSihua": palace_sihua,
        "xiaoXian": xiaoXian,
        "liuNianSihua": liuNianSihua,
        "liuNianSihuaRange": liuNianSihuaRange,
        "liuYueSihua": liuYueSihua,
        "liuYueSihuaByYear": liuYueSihuaByYear,
        "liuNianPan": liuNianPan,
    }
