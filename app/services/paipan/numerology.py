"""数字命理排盘 —— 原型 JS 算法移植（oraclemind/src/data/numerologyData.ts + page.tsx computeNum）。

与前端行为保持严格一致：
- digital_root    数字根（逐位相加直到个位数）
- num_grid_counts 九宫格统计（年月日所有数字 1~9 出现次数）
- compute_num     完整排盘：生命灵数 / 生日数 / 九宫格 / 缺数 / 未来 5 年流年 / 数字解读
"""

from __future__ import annotations

from datetime import date

from app.services.paipan.pinyin_data import hanzi_to_pinyin

# ===== 1~9 数字完整解读（移植自 NUM_DATA）=====
NUM_DETAILS: dict[int, dict[str, str]] = {
    1: {"name": "开创者", "element": "火", "color": "红 · 金", "keywords": "独立 · 领导 · 创造 · 自信",
        "talent": "开创与决断", "lesson": "学会合作与倾听", "career": "创业者 · 管理者 · 设计师", "mate": "4、6 号人最合拍",
        "posi": "自信果敢、行动力强", "nega": "固执独断、欠缺耐心",
        "desc": "1 是万物的起点。你天生带着开创的能量，敢于从 0 到 1，是天生的开拓者。人生课题在于：在坚定自我与接纳他人之间找到平衡，学会把「我」变成「我们」。"},
    2: {"name": "调和者", "element": "水", "color": "蓝 · 银", "keywords": "合作 · 平衡 · 细腻 · 直觉",
        "talent": "协调与共情", "lesson": "避免过度依赖他人", "career": "外交 · 咨询 · 护理 · 艺术", "mate": "4、8 号人最合拍",
        "posi": "温柔包容、洞察人心", "nega": "优柔寡断、易被影响",
        "desc": "2 是关系的桥梁。你天生敏感细腻，擅长感受氛围、调和矛盾，是团队里天然的润滑剂。人生课题在于：把自己的感受也放在同等重要的位置，学会说不。"},
    3: {"name": "表达者", "element": "木", "color": "黄 · 橙", "keywords": "表达 · 创意 · 社交 · 乐观",
        "talent": "表达与创造", "lesson": "专注深耕、不浅尝辄止", "career": "写作 · 演艺 · 营销 · 设计", "mate": "1、5 号人最合拍",
        "posi": "才华外放、感染力强", "nega": "浮夸散漫、三分钟热度",
        "desc": "3 是语言的魔法师。你天生善于表达、灵感源源不断，走到哪里都是气氛中心。人生课题在于：把喷涌的创意沉淀成作品，学会在一件事上扎下根。"},
    4: {"name": "建造者", "element": "土", "color": "绿 · 棕", "keywords": "稳定 · 执行 · 秩序 · 可靠",
        "talent": "规划与执行", "lesson": "学会灵活应变", "career": "工程 · 财务 · 行政 · 法律", "mate": "2、7 号人最合拍",
        "posi": "踏实可靠、步步为营", "nega": "僵化固执、抗拒变化",
        "desc": "4 是大地的建造者。你天生可靠、注重秩序，能把想法一步步落地成现实，是所有人最信任的伙伴。人生课题在于：在规则与变化之间留出弹性，接受世界的不可控。"},
    5: {"name": "探索者", "element": "火", "color": "红 · 紫", "keywords": "自由 · 冒险 · 应变 · 好奇",
        "talent": "适应与突破", "lesson": "学会坚持与承担", "career": "旅行 · 销售 · 媒体 · 公关", "mate": "3、9 号人最合拍",
        "posi": "灵活机智、拥抱变化", "nega": "逃避责任、难以安定",
        "desc": "5 是风中的旅人。你天生向往自由、对新事物永远好奇，危机在你眼里都是转机。人生课题在于：在自由和承诺之间找到平衡，让冒险有归处。"},
    6: {"name": "守护者", "element": "金", "color": "粉 · 白", "keywords": "责任 · 关爱 · 完美 · 疗愈",
        "talent": "照顾与疗愈", "lesson": "接受不完美、适度放手", "career": "教育 · 医护 · 家装 · 心理", "mate": "1、9 号人最合拍",
        "posi": "温暖负责、为爱付出", "nega": "过度操心、自我牺牲",
        "desc": "6 是家的守护星。你天生有强烈的责任感与爱的能力，总想为在乎的人撑起一片天。人生课题在于：爱别人的同时也爱自己，学会接受世间本无完美。"},
    7: {"name": "智慧探索者", "element": "水", "color": "靛 · 紫", "keywords": "思考 · 洞察 · 灵性 · 独立",
        "talent": "分析与洞察", "lesson": "学会信任直觉", "career": "研究 · 科技 · 哲学 · 玄学", "mate": "2、5 号人最合拍",
        "posi": "深邃冷静、看透本质", "nega": "孤僻多疑、封闭自我",
        "desc": "7 是夜空的观星者。你天生具备深刻的洞察力和分析能力，是天生的研究者和思考者。人生课题在于：学会信任直觉，在理性与灵性之间找到平衡。"},
    8: {"name": "掌舵者", "element": "土", "color": "黑 · 金", "keywords": "权力 · 财富 · 掌控 · 格局",
        "talent": "统筹与创造财富", "lesson": "平衡物质与精神", "career": "金融 · 管理 · 法律 · 创业", "mate": "2、6 号人最合拍",
        "posi": "有魄力、格局宏大", "nega": "控制欲强、易被欲望牵引",
        "desc": "8 是王座的掌权者。你天生对资源和权力敏感，有把事业做大做强的格局与手腕。人生课题在于：让财富与权力为更大的善意服务，别被数字定义。"},
    9: {"name": "圆满者", "element": "火", "color": "白 · 红", "keywords": "大爱 · 智慧 · 放下 · 慈悲",
        "talent": "感召与成就他人", "lesson": "学会放手的艺术", "career": "公益 · 艺术 · 导师 · 慈善", "mate": "3、6 号人最合拍",
        "posi": "胸怀宽广、悲天悯人", "nega": "过度理想化、容易心累",
        "desc": "9 是旅程的终点站。你天生带着大爱与智慧，看得懂全局，也愿意成就别人。人生课题在于：学会放下不属于自己的责任，让慈悲不变成负担。"},
    # ===== 大师数（能量翻倍，不化简）=====
    11: {"name": "启蒙者", "element": "光", "color": "银 · 紫", "keywords": "直觉 · 灵性 · 启发 · 洞见",
         "talent": "灵感与灵性觉察", "lesson": "安顿敏感的神经、化焦虑为洞见", "career": "疗愈 · 艺术 · 灵性引导 · 咨询", "mate": "2、9 号人最合拍",
         "posi": "直觉敏锐、灵光乍现", "nega": "神经紧绷、想太多而内耗",
         "desc": "11 是放大版的 2，也是连接天地的「灵性天线」。你天生带着远超常人的直觉与洞察，常常一句话就点醒别人。人生课题在于：别被过强的感应烧坏自己——学会落地、休息、把灵感变成可执行的表达，而非困在焦虑里。"},
    22: {"name": "建造者", "element": "土", "color": "金 · 靛", "keywords": "格局 · 落地 · 统筹 · 远见",
         "talent": "把愿景建成现实", "lesson": "在宏大与实操间找到节奏", "career": "建筑 · 创业 · 公益组织 · 战略", "mate": "4、8 号人最合拍",
         "posi": "格局宏大、能扛大事", "nega": "压力过载、想得大却动不了",
         "desc": "22 是放大版的 4，被称为「大师建造者」。你不仅能想，更能把别人的梦想、甚至整个社群的福祉，一砖一瓦落地成真。人生课题在于：别被「非做大不可」压垮——允许自己从小处起步，稳健比规模更重要。"},
    33: {"name": "疗愈师", "element": "爱", "color": "白 · 粉", "keywords": "慈悲 · 疗愈 · 奉献 · 引领",
         "talent": "抚慰与光照他人", "lesson": "在付出与自爱间守住边界", "career": "心理 · 教育 · 医护 · 公益", "mate": "6、9 号人最合拍",
         "posi": "温暖有力量、治愈人心", "nega": "过度牺牲、背负他人命运",
         "desc": "33 是放大版的 6，被称为「大师疗愈师」。你天生带着深厚的慈悲，像一盏灯，走到哪里都能照亮、安抚身边的人。人生课题在于：疗愈别人之前先疗愈自己——你不必背负所有人的命运，温柔也要有边界。"},
}

# ===== 流年数字 → 年度主题（移植自 YEAR_MEANING）=====
YEAR_MEANINGS: dict[int, str] = {
    1: "🌱 新开始年：开启新篇章，适合制定计划、启动新项目",
    2: "🌊 等待年：节奏放慢，合作与沉淀，不宜冒进",
    3: "🎭 表达年：社交活跃、创意表达，是被看见的一年",
    4: "🏗️ 建设年：打基础、稳扎稳打，努力开始有回报",
    5: "🌀 变动年：变化与机会流动，灵活应变、敢于尝试",
    6: "❤️ 责任年：家庭感情与责任成为重心，付出与平衡",
    7: "🔭 内省年：向内探索、学习修行，适合独处思考",
    8: "👑 收获年：事业财运迎来回报，掌控与成就之年",
    9: "🎆 完结年：收尾与放下，为下一个十年做准备",
}

# ===== 数字 → 幸运色（移植自 NUM_COLORS）=====
NUM_COLORS: dict[int, str] = {
    1: "红 · 金", 2: "蓝 · 银", 3: "黄 · 橙", 4: "绿 · 棕", 5: "红 · 紫",
    6: "粉 · 白", 7: "靛 · 紫", 8: "黑 · 金", 9: "白 · 红",
    11: "银 · 紫", 22: "金 · 靛", 33: "白 · 粉",
}


def digital_root(n: int, keep_master: bool = False) -> int:
    """数字根：逐位相加直到个位数（与前端 digitalRoot 一致）。

    keep_master=True 时保留 11/22/33 大师数不化简（毕达哥拉斯体系能量最高的一类）。
    """
    while n > 9:
        if keep_master and n in (11, 22, 33):
            return n
        s = 0
        while n > 0:
            s += n % 10
            n //= 10
        n = s
    if keep_master and n in (11, 22, 33):
        return n
    return n


def num_grid_counts(year: int, month: int, day: int) -> dict[int, int]:
    """统计年/月/日所有数字在 1~9 中出现的次数（九宫格）。"""
    s = f"{year}{month}{day}"
    counts: dict[int, int] = {i: 0 for i in range(1, 10)}
    for ch in s:
        if "1" <= ch <= "9":
            counts[int(ch)] += 1
    return counts


# ==== 毕达哥拉斯核心数字（P1-4，与前端 numerologyData.ts 严格对齐）====
# 字母 → 数值：A=1…I=9 循环；元音取 A/E/I/O/U（Y 归辅音）。

LETTER_VALUE: dict[str, int] = {
    c: (i % 9) + 1 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
}
VOWELS = frozenset("aeiou")


def name_numbers(pinyin: str) -> dict[str, int] | None:
    """拼音串 → 表现数 / 内驱数 / 人格数（大师数保留）。"""
    letters = [c for c in pinyin.lower() if c.isascii() and c.isalpha()]
    if not letters:
        return None

    def total(pred) -> int:
        return sum(LETTER_VALUE[c.upper()] for c in letters if pred(c))

    return {
        "expression": digital_root(total(lambda c: True), keep_master=True),
        "soulUrge": digital_root(total(lambda c: c in VOWELS), keep_master=True),
        "personality": digital_root(total(lambda c: c not in VOWELS), keep_master=True),
    }


YEAR_SPAN = 9  # 流年跨度：覆盖一个完整数字周期 1-9


def compute_challenge(year: int, month: int, day: int) -> dict[str, int]:
    """挑战数（4 个）：月 / 日 / 年各自化到个位后的两两差值。"""
    mo, da, ye = digital_root(month), digital_root(day), digital_root(year)
    c1, c2, c4 = abs(mo - da), abs(da - ye), abs(mo - ye)
    return {"c1": c1, "c2": c2, "c3": abs(c1 - c2), "c4": c4}


# 挑战数 0~8 解读（与前端 CHALLENGE_DATA 保持一致，后端保留一份以便接口自洽）
CHALLENGE_DATA: dict[int, dict[str, str]] = {
    0: {"name": "无碍", "desc": "这一层几乎没有阻力，能量自然流动。风险是缺少张力带来的推力——容易安于现状、动力不足，需要自己给自己设目标。"},
    1: {"name": "自我 vs 他人", "desc": "在「坚持自己」与「在意他人眼光」之间摇摆。要么过度迎合失去自我，要么过度自我显得独断。课题是：先站稳自己，再从容合作。"},
    2: {"name": "亲密 vs 依赖", "desc": "害怕亲密又害怕孤单，容易在关系里过度付出或过度退缩。课题是：学会平等地依赖与被依赖，把关系当成选择而不是需要。"},
    3: {"name": "表达 vs 自我怀疑", "desc": "想说却不敢说，或一说就停不下来。创造力被自我审查卡住。课题是：允许自己「先表达、再完美」，把作品做完比做好更重要。"},
    4: {"name": "秩序 vs 束缚", "desc": "要么缺乏耐心、做事虎头蛇尾，要么被规则和计划捆死、害怕失控。课题是：建立节奏而非枷锁，允许计划被打乱后重建。"},
    5: {"name": "自由 vs 承诺", "desc": "渴望自由又渴望归属，临近承诺就想逃，逃开后又空虚。课题是：把「自由」重新定义为「选择自己想要的责任」，而不是无负担。"},
    6: {"name": "完美 vs 接纳", "desc": "对己对人的标准过高，容易失望、挑剔、替别人背责任。课题是：把标准从「完美」下调到「够好」，允许自己和他人带着瑕疵前行。"},
    7: {"name": "信任 vs 怀疑", "desc": "要么过度多疑、把人都推开，要么轻信后被伤害。课题是：把怀疑用在验证上而不是预设上——给证据，再下判断。"},
    8: {"name": "掌控 vs 焦虑", "desc": "对金钱、权力、地位有深层焦虑，容易用力过猛或干脆逃避。课题是：把「掌控感」从外部成就搬回内在节奏，先稳住自己的节奏再谈规模。"},
}


def compute_core(year: int, month: int, day: int, life_path: int, name: str | None) -> dict:
    """核心数字（表现 / 内驱 / 人格 / 成熟 + 四挑战）。

    name 为空或无法转拼音时，只返回挑战数（姓名三项为 None）。
    """
    challenge = compute_challenge(year, month, day)
    empty: dict[str, object] = {
        "pinyin": "", "unmatched": [],
        "expression": None, "soulUrge": None, "personality": None, "maturity": None,
        "challenge": challenge,
    }
    if not name or not name.strip():
        return empty
    py = hanzi_to_pinyin(name.strip())
    nums = name_numbers(py.text)
    if not nums:
        return {**empty, "pinyin": py.text, "unmatched": py.unmatched}
    return {
        "pinyin": py.text,
        "unmatched": py.unmatched,
        "expression": nums["expression"],
        "soulUrge": nums["soulUrge"],
        "personality": nums["personality"],
        "maturity": digital_root(life_path + nums["expression"], keep_master=True),
        "challenge": challenge,
    }


def compute_num(year: int, month: int, day: int, today: date | None = None, name: str | None = None) -> dict:
    """完整数字命理排盘（与前端 computeNum 输出结构一致）。

    入参为「农历生日」数字（年/月/日），算法与前端完全对齐：
    - life_path  生命灵数 = digital_root(年 + 月 + 日)
    - birthday_num 生日数 = digital_root(日)
    - counts     九宫格统计
    - missing    缺数（出现 0 次的数字）
    - years      以今年为起点的未来 9 年流年（覆盖一个完整数字周期 1-9）
    - data       生命灵数对应的完整解读
    - core       核心数字（表现 / 内驱 / 人格 / 成熟 + 四挑战），name 为空时只含挑战数

    name 为可选中文姓名，用于计算表现数 / 内驱数 / 人格数 / 成熟数。
    """
    life_path = digital_root(year + month + day, keep_master=True)
    birthday_num = digital_root(day, keep_master=True)
    counts = num_grid_counts(year, month, day)
    missing = sorted(k for k, v in counts.items() if v == 0)

    now = (today or date.today()).year
    years: list[dict] = []
    for i in range(YEAR_SPAN):
        yr = now + i
        digit_sum = month + day + sum(int(c) for c in str(yr))
        py = digital_root(digit_sum)
        years.append({
            "yr": yr,
            "py": py,
            "tag": YEAR_MEANINGS[py].split("：")[0],
            "isCurrent": i == 0,
        })

    return {
        "lifePath": life_path,
        "birthdayNum": birthday_num,
        "counts": counts,
        "missing": missing,
        "years": years,
        "data": NUM_DETAILS[life_path],
        "core": compute_core(year, month, day, life_path, name),
    }
