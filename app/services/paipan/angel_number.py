# -*- coding: utf-8 -*-
"""天使数字（Angel Numbers）服务端权威实现。

口径严格对齐前端 ``oraclemind/src/data/angelNumbers.ts`` —— 释义表逐条搬运，
解析优先级与归一化规则与前端 ``parseAngelNumber()`` 完全一致，**不自创含义**。
前端仍保留本地 ``angelNumbers.ts`` 作为后端不可用时的降级兜底，两份数据必须同步改动。

体系说明：天使数字属西方数字象征学（numerology 的民俗分支），认为反复出现的
数字序列是潜意识 / 守护力量的提示。与生命灵数（毕达哥拉斯体系）同源但口径不同 ——
天使数字看「重复出现的序列」本身，生命灵数看「约减后的根数」。
结论仅供参考与自我觉察，不构成任何决策依据。
"""

from __future__ import annotations

import re
from collections import Counter

# ============================================================================
# 释义表（与前端 ANGEL_NUMBERS 逐条一致，字段命名保持 camelCase）
# ============================================================================

ANGEL_NUMBERS: dict[str, dict] = {
    "000": {
        "n": "000",
        "title": "源头 · 一切归零",
        "core": "你正与宇宙本源同频，一个循环的结束与另一个循环的开始同时发生。0 放大它旁边的能量，这里代表「无限的可能」与「提醒你本自具足」。",
        "advice": "适合清空旧计划、做断舍离。别急着填满空白——此刻的「空」本身就是孕育期。",
        "love": "关系进入重新定义期，单身者宜先与自己和解。",
        "career": "旧项目收尾，新方向尚未显形，宜蓄力不宜强攻。",
    },
    "111": {
        "n": "111",
        "title": "念头显化 · 门户开启",
        "core": "你的想法正在以极快速度显化，111 是最著名的「留意你的念头」提醒。宇宙在说：你关注什么，就在召唤什么。",
        "advice": "接下来 24 小时刻意只关注想要的，而非害怕的。把想法写下来，它会比平时更快落地。",
        "love": "新缘分可能在意想不到的场合出现，主动一点。",
        "career": "新机会的入口已开，勇敢提出方案，别自我否定。",
    },
    "222": {
        "n": "222",
        "title": "信任 · 合作 · 平衡",
        "core": "事情正在幕后推进，表面没动静不代表没进展。222 提醒你保持信心、与人协作，并照顾好身心的平衡。",
        "advice": "把焦虑换成耐心。遇到卡点时找人商量，而不是独自硬扛。",
        "love": "关系需要双向奔赴，若长期单方付出，该谈一谈了。",
        "career": "合伙、谈判、团队协作有利，避免独断。",
    },
    "333": {
        "n": "333",
        "title": "表达 · 创意 · 扬升",
        "core": "指导灵与高我与你同在，333 鼓励你把内在的东西表达出来——写作、演讲、创作，或说出一句早就该说的话。",
        "advice": "别压抑表达欲。有话直说，有作品就发出去，被看见的时机到了。",
        "love": "坦诚沟通能化解误会，暧昧宜挑明。",
        "career": "创意、内容、表达类工作进入高产期，把握流量窗口。",
    },
    "444": {
        "n": "444",
        "title": "根基 · 守护 · 踏实",
        "core": "你被守护着，444 代表稳固的地基与来自守护力量的支持。它提醒你：慢就是快，把基础打牢。",
        "advice": "专注执行与积累，别频繁换方向。健康、财务、作息这些「地基」值得优先投入。",
        "love": "关系趋向稳定，适合谈长期承诺。",
        "career": "宜做制度化、流程化建设，短期不见效但长期复利高。",
    },
    "555": {
        "n": "555",
        "title": "变化 · 转折 · 自由",
        "core": "重大变化正在发生或即将发生。555 是「系好安全带」的信号，变化未必舒服，但通常是必要的。",
        "advice": "拥抱变化而非抵抗。清理不再服务于你的人事物，为新的腾出位置。",
        "love": "关系格局可能变动，旧模式难以为继，坦诚面对。",
        "career": "转岗/转型/搬迁的概率上升，顺势而为比死守更明智。",
    },
    "666": {
        "n": "666",
        "title": "回归 · 照顾 · 平衡付出",
        "core": "666 并非不祥，它提醒你把注意力从外在拉回内在与生活：家庭、健康、被忽略的情绪，以及过度付出的问题。",
        "advice": "检查一下自己是否在某段关系或工作中付出失衡。先照顾好自己，再照顾别人。",
        "love": "容易过度付出或过度索取，回到五五开。",
        "career": "避免为了讨好而承接超出职责的事，学会说「不」。",
    },
    "777": {
        "n": "777",
        "title": "幸运 · 内在智慧 · 精进",
        "core": "你走在正确的路上。777 是强烈的好运与确认信号，也代表学习、研究、灵性成长进入收获期。",
        "advice": "继续做你正在做的事，别因短期没结果而放弃。适合深度学习与技能精进。",
        "love": "单身者桃花运上升；有伴者宜共同成长、一起上课或旅行。",
        "career": "努力即将被看见，考证、进修、答辩等有利。",
    },
    "888": {
        "n": "888",
        "title": "丰盛 · 收获 · 因果闭环",
        "core": "丰盛正在流向你，888 对应财富与成果的兑现，也是「种瓜得瓜」的收成期。它提醒你：流动起来才不会堵。",
        "advice": "该收的账去收，该谈的薪资去谈。同时保持给予——财富是流动的能量。",
        "love": "关系进入成熟期，谈婚论嫁、共同置业有利。",
        "career": "业绩、回款、升职加薪的窗口期，主动争取。",
    },
    "999": {
        "n": "999",
        "title": "完成 · 放下 · 服务他人",
        "core": "一个周期走到终点，999 是关于「结束」与「交棒」的数字。放下不再适合的，才能迎接新的。",
        "advice": "做收尾与告别：结束项目、断掉消耗你的关系、捐出闲置。完成比完美重要。",
        "love": "该放手的放手，纠缠只会延长痛苦。",
        "career": "项目结项、阶段总结，把经验沉淀成方法论或带教他人。",
    },
    "1234": {
        "n": "1234",
        "title": "循序渐进 · 按部就班",
        "core": "事情会按步骤推进，1234 是「一切正在有序展开」的确认。别跳步，也别急。",
        "advice": "把大目标拆成 1-2-3-4 步，一步步走完。",
        "career": "适合做计划、排期、打基础。",
    },
    "1111": {
        "n": "1111",
        "title": "觉醒之门 · 强烈显化",
        "core": "111 的加强版，被视为「通往高维的门户」。此刻你的显化能力处在峰值，起心动念都会被放大。",
        "advice": "看到 11:11 时停一下，留意脑中第一个念头——那正是你该聚焦的方向。",
        "love": "双生火焰/灵魂伴侣类连结的信号，留意新出现的人。",
    },
    "1212": {
        "n": "1212",
        "title": "灵性成长 · 保持正向",
        "core": "提醒你把日常与更高的目标对齐。1212 是「你的生活方式需要升级」的温和提示。",
        "advice": "调整作息与习惯，让日常节奏配得上你的野心。",
    },
    "1010": {
        "n": "1010",
        "title": "新周期 · 无限潜能",
        "core": "1 与 0 的组合放大了「开始 × 无限」，代表一个全新层次即将开启。",
        "advice": "设定新目标的最佳时机，把想法落到具体行动上。",
    },
}

# 单位数字释义（天使数字口径，用于拆解序列中的每一位）—— 与前端 ANGEL_DIGIT_MEANING 一致
ANGEL_DIGIT_MEANING: dict[int, str] = {
    0: "无限与源头，放大相邻数字的能量",
    1: "新的开始、主动、独立",
    2: "合作、信任、平衡与耐心",
    3: "表达、创意、喜悦与社交",
    4: "稳定、秩序、踏实与根基",
    5: "变化、自由、冒险与转折",
    6: "责任、照顾、家庭与疗愈",
    7: "智慧、内省、灵性与幸运",
    8: "丰盛、权力、成果与流通",
    9: "完成、慈悲、放手与奉献",
}

# ============================================================================
# 输入归一化边界
# ============================================================================

#: 归一化后允许的最大位数。超过此长度的输入不再视为天使数字序列
#: （天使数字的实际形态一般 2~6 位，放宽到 12 位以容纳「20261111」这类日期串）。
ANGEL_MAX_DIGITS = 12

#: 序列分析（analyze_sequence）允许的最大条目数，防止一次灌入海量数据。
ANALYZE_MAX_ITEMS = 100

_DIGIT_RE = re.compile(r"\d")


def normalize_angel_input(raw: str) -> str:
    """归一化：只保留数字字符（"11:11" → "1111"、"1 1 1" → "111"、"0011" → "0011"）。

    对 non-str 入参（None / 数字 / 容器）做安全兜底：强制 ``str()`` 后再抽取，
    避免 ``ValueError`` 之外的 ``TypeError``（路由层已用 pydantic 锁死为 str，
    此兜底仅为服务层直接调用时的健壮性，确保不会触发 500）。
    """
    return "".join(_DIGIT_RE.findall(str(raw or "")))


def digital_root(n: int) -> int:
    """数字根：反复求和到个位（0 保持 0）。与前端 digitalRoot 一致。"""
    if n == 0:
        return 0
    r = n % 9
    return 9 if r == 0 else r


def _is_rep_digit(nums: list[int]) -> bool:
    """是否全同数字（如 222 / 2222）。单字符不算（与前端一致）。"""
    return len(nums) > 1 and all(d == nums[0] for d in nums)


def _is_sequence(nums: list[int]) -> bool:
    """是否连续递增序列（如 1234、456、890 —— 9 之后回绕到 0）。"""
    if len(nums) < 3:
        return False
    return all(i == 0 or d == (nums[i - 1] + 1) % 10 for i, d in enumerate(nums))


def _match_key(raw: str, nums: list[int]) -> str:
    """按前端优先级匹配词条 key：精确命中 → 全同数字压到三位 → 前四位 → 数字根兜底。"""
    if raw in ANGEL_NUMBERS:
        return raw
    if _is_rep_digit(nums):
        k = str(nums[0]) * 3
        if k in ANGEL_NUMBERS:
            return k
    if raw[:4] in ANGEL_NUMBERS:
        return raw[:4]
    root = digital_root(sum(nums))
    k = str(root) * 3
    return k if k in ANGEL_NUMBERS else "111"


def parse_angel_number(raw: str) -> dict:
    """解析天使数字，返回与前端 ``AngelResult`` 同构的结果。

    :param raw: 原始输入，可为 "1111" / "11:11" / "1 2 3" / 带空格或分隔符的任意串
    :returns: dict，字段见下（camelCase，供前端直接消费）
    :raises ValueError: 输入不含任何数字，或归一化后位数超过 :data:`ANGEL_MAX_DIGITS`
    """
    normalized = normalize_angel_input(raw)
    if not normalized:
        raise ValueError("请输入至少一个数字（如 1111 / 11:11）")
    if len(normalized) > ANGEL_MAX_DIGITS:
        raise ValueError(f"数字序列过长（最多 {ANGEL_MAX_DIGITS} 位）")

    nums = [int(c) for c in normalized]
    digits: list[int] = []
    for d in nums:  # 去重保序（用 dict.fromkeys 会丢类型提示，这里显式保序）
        if d not in digits:
            digits.append(d)

    is_rep = _is_rep_digit(nums)
    key = _match_key(normalized, nums)

    return {
        "raw": normalized,
        "key": key,
        "entry": ANGEL_NUMBERS[key],
        "isRepDigit": is_rep,
        "isSequence": _is_sequence(nums),
        "digits": digits,
        # 重复数字：仅全同序列时给出（如 2222 → 2），其余为 None
        "repDigit": nums[0] if is_rep else None,
        # 主数字（数字根）：未精确命中词条时的兜底口径，前端亦按此推导
        "digitalRoot": digital_root(sum(nums)),
        "digitMeaning": {str(d): ANGEL_DIGIT_MEANING[d] for d in digits},
    }


def analyze_sequence(numbers: list[str]) -> dict:
    """分析「近期反复看到的多个数字」这一段序列。

    统计每个序列的出现频次、归纳主题关键词（取自命中词条的 title 分词），
    用于回答「我最近到底在被提醒什么」。

    :param numbers: 原始输入列表，每项都会走 :func:`normalize_angel_input`
    :raises ValueError: 列表为空、超过 :data:`ANALYZE_MAX_ITEMS`，或全部条目无有效数字
    """
    if not numbers:
        raise ValueError("请至少记录一个数字")
    if len(numbers) > ANALYZE_MAX_ITEMS:
        raise ValueError(f"一次最多分析 {ANALYZE_MAX_ITEMS} 条记录")

    raw_counter: Counter[str] = Counter()
    key_counter: Counter[str] = Counter()
    digit_counter: Counter[int] = Counter()
    invalid: list[str] = []
    parsed: dict[str, dict] = {}

    for item in numbers:
        normalized = normalize_angel_input(item)
        if not normalized or len(normalized) > ANGEL_MAX_DIGITS:
            invalid.append(item if isinstance(item, str) else str(item))
            continue
        if normalized not in parsed:
            parsed[normalized] = parse_angel_number(normalized)
        raw_counter[normalized] += 1
        for d in normalized:
            digit_counter[int(d)] += 1
        key_counter[parsed[normalized]["key"]] += 1

    total = sum(raw_counter.values())
    if total == 0:
        raise ValueError("没有解析到任何有效数字")

    # 频次表（降序；同频次按数字串字典序稳定排列）
    items = [
        {
            "raw": r,
            "count": c,
            "ratio": round(c / total, 4),
            "key": parsed[r]["key"],
            "title": parsed[r]["entry"]["title"],
            "isRepDigit": parsed[r]["isRepDigit"],
            "isSequence": parsed[r]["isSequence"],
        }
        for r, c in sorted(raw_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    # 出现次数最多的序列（可能并列）
    max_count = items[0]["count"]
    top = [it for it in items if it["count"] == max_count]

    # 主题关键词：按「命中词条 × 出现次数」加权，取 title 的分词（"念头显化 · 门户开启"）
    theme_weight: Counter[str] = Counter()
    for key, c in key_counter.items():
        for token in ANGEL_NUMBERS[key]["title"].split("·"):
            token = token.strip()
            if token:
                theme_weight[token] += c
    themes = [t for t, _ in sorted(theme_weight.items(), key=lambda kv: (-kv[1], kv[0]))]

    # 主导词条 = 出现次数最多的命中词条
    top_key, top_key_count = sorted(key_counter.items(), key=lambda kv: (-kv[1], kv[0]))[0]

    repeated = sum(c for r, c in raw_counter.items() if len(r) > 1 and _is_rep_digit([int(x) for x in r]))
    summary = (
        f"共 {total} 条记录，出现最多的是 {top[0]['raw']}（{max_count} 次），"
        f"主导提示为「{ANGEL_NUMBERS[top_key]['title']}」。"
    )
    if repeated:
        summary += f"其中 {repeated} 条为全同重复数，提醒强度更高。"

    return {
        "total": total,
        "unique": len(items),
        "invalid": invalid,
        "items": items,
        "top": top,
        "topKey": top_key,
        "topEntry": ANGEL_NUMBERS[top_key],
        "themes": themes,
        "keyFrequency": dict(sorted(key_counter.items(), key=lambda kv: (-kv[1], kv[0]))),
        "digitFrequency": {str(d): c for d, c in sorted(digit_counter.items(), key=lambda kv: (-kv[1], kv[0]))},
        "summary": summary,
    }


def compute_angel_number(birth_date, name: str | None = None) -> dict:
    """从生日推导「个人天使数字」。

    ⚠️ 算法依据说明：天使数字本身**没有**典籍化的个人推算法。这里的推导
    **仅按生命数法（数字根）** —— 把出生年月日各位数字反复求和到个位，
    再映射到三位重复数词条（如生命数 7 → '777'）。属**民俗算法**，
    不属于任何古典命理体系，请勿当作命理结论使用。

    :param birth_date: ``datetime.date`` 或 "YYYY-MM-DD" / "YYYYMMDD" 字符串
    :param name: 可选姓名；**不参与计算**，仅回显（姓名数属毕达哥拉斯体系，
                 与天使数字口径不同，本函数不混用，避免编造口径）
    """
    if hasattr(birth_date, "year") and hasattr(birth_date, "month") and hasattr(birth_date, "day"):
        y, m, d = birth_date.year, birth_date.month, birth_date.day  # type: ignore[union-attr]
    else:
        digits = normalize_angel_input(str(birth_date))
        if len(digits) != 8:
            raise ValueError("出生日期需为 YYYY-MM-DD / YYYYMMDD")
        y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])

    life_path = digital_root(sum(int(c) for c in f"{y:04d}{m:02d}{d:02d}"))
    birthday_num = digital_root(d)
    key = str(life_path) * 3
    if key not in ANGEL_NUMBERS:
        key = "111"

    return {
        "birthDate": f"{y:04d}-{m:02d}-{d:02d}",
        "name": (name or "").strip(),
        "lifePath": life_path,
        "birthdayNum": birthday_num,
        "key": key,
        "entry": ANGEL_NUMBERS[key],
        "personalNumber": str(life_path) * 3,
        "note": "仅按生命数法（数字根）推导，属民俗算法，非典籍命理结论。",
    }
