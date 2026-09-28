"""量表目录 —— 右轨心理学产品的结构化测评定义（服务端权威，客户端只取题目不取答案）。

合规定位（2026-09-19）：
- 全部为「自我觉察 / 成长导向」量表，**非诊断、非病理、不替代专业帮助**；
- 量表选题优先公共领域（IPIP 系列），规避 MBTI / PHQ-9 等需授权或需法务确认的版权风险；
- 题目与计分规则以服务端为准，客户端不可伪造题干或篡改计分。

首个落地量表：IPIP 大五（Mini-IPIP，Donnellan et al. 2006，公共领域，20 题）。
后续可在此注册更多量表（如四维人格偏好 / 情绪状态自评），前端按 slug 拉取。
"""

from __future__ import annotations

from typing import Any

# Likert 五点量表（1=非常不同意 … 5=非常同意）
LIKERT_5: list[dict[str, Any]] = [
    {"value": 1, "label": "非常不符合"},
    {"value": 2, "label": "不太符合"},
    {"value": 3, "label": "说不清"},
    {"value": 4, "label": "比较符合"},
    {"value": 5, "label": "非常符合"},
]

# 五个维度：key / 名称 / 正向含义（高分代表什么）/ 低分含义（低分代表什么）
_DIMENSIONS: list[dict[str, Any]] = [
    {
        "key": "E", "name": "外向性", "low_name": "内敛", "high_name": "外倾",
        "low": "你更偏好独处与安静的小范围联结，能量多来自内在世界；这让你在深度关系与专注思考上更有优势。",
        "mid": "你能在独处与社交之间灵活切换，视情境与状态调整自己的参与方式。",
        "high": "你在人际互动中更主动、更容易从与人联结中获得能量；适度留白能让你保持平衡。",
    },
    {
        "key": "A", "name": "宜人性", "low_name": "独立", "high_name": "亲和",
        "low": "你更看重独立判断与直率，不轻易迎合；把善意留给真正在意的人，是你的方式。",
        "mid": "你能在合作与坚持自我之间取得平衡，既顾及他人也守住边界。",
        "high": "你天然体谅他人、愿意协作，这为你积累了不少信任与善意；偶尔也要记得照顾自己的需求。",
    },
    {
        "key": "C", "name": "尽责性", "low_name": "随性", "high_name": "条理",
        "low": "你更随性、灵活，擅长在变动中临场发挥；给重要的事设一两个锚点，会让你更从容。",
        "mid": "你既有计划性也能接受变化，多数时候能把事情稳稳兜住。",
        "high": "你靠谱、有条理、习惯把事情提前收尾；注意别让“必须做好”变成对自己的紧绷。",
    },
    {
        "key": "N", "name": "情绪稳定性", "low_name": "敏感", "high_name": "平稳",
        "low": "你对情绪与环境更敏感，这让你共情力强、觉察细腻；给情绪一个出口，它会成为你的资源而非负担。",
        "mid": "你的情绪有起伏但总体可控，能在波动后较快回到自己的节奏。",
        "high": "你大多数时候平稳松弛，不容易被情绪裹挟；这是很稳的底盘。",
    },
    {
        "key": "O", "name": "开放性", "low_name": "务实", "high_name": "求新",
        "low": "你更务实、偏好具体可感的事物，脚踏实地的风格让你不易被概念带偏。",
        "mid": "你对新想法与熟悉经验都保持开放，能按需要切换视角。",
        "high": "你好奇、爱想象、乐于接触新观念；把发散的灵感落到一两个小行动，会更有获得感。",
    },
]

# Mini-IPIP 20 题（公共领域）：dimension 取维度 key，reverse=True 为反向计分题
_ITEMS: list[dict[str, Any]] = [
    {"id": "E1", "dimension": "E", "reverse": False, "text": "我是聚会里很能带动气氛的人。"},
    {"id": "E2", "dimension": "E", "reverse": True, "text": "我不太爱主动说话。"},
    {"id": "E3", "dimension": "E", "reverse": False, "text": "在聚会上我会和很多不同的人交谈。"},
    {"id": "E4", "dimension": "E", "reverse": True, "text": "我倾向于待在不引人注目的位置。"},
    {"id": "A1", "dimension": "A", "reverse": False, "text": "我能体谅他人的感受。"},
    {"id": "A2", "dimension": "A", "reverse": True, "text": "我对别人的烦恼不太关心。"},
    {"id": "A3", "dimension": "A", "reverse": False, "text": "我能感受到别人当时的情绪。"},
    {"id": "A4", "dimension": "A", "reverse": True, "text": "我对他人本身没什么兴趣。"},
    {"id": "C1", "dimension": "C", "reverse": False, "text": "我会把该做的事立刻做完。"},
    {"id": "C2", "dimension": "C", "reverse": True, "text": "我常忘记把东西放回原处。"},
    {"id": "C3", "dimension": "C", "reverse": False, "text": "我喜欢做事井井有条。"},
    {"id": "C4", "dimension": "C", "reverse": True, "text": "我常把事情弄得一团糟。"},
    {"id": "N1", "dimension": "N", "reverse": False, "text": "我的情绪起伏比较大。"},
    {"id": "N2", "dimension": "N", "reverse": True, "text": "大多数时候我都很放松。"},
    {"id": "N3", "dimension": "N", "reverse": False, "text": "我很容易感到心烦。"},
    {"id": "N4", "dimension": "N", "reverse": True, "text": "我很少感到沮丧。"},
    {"id": "O1", "dimension": "O", "reverse": False, "text": "我有很丰富的想象力。"},
    {"id": "O2", "dimension": "O", "reverse": True, "text": "我很难理解抽象的概念。"},
    {"id": "O3", "dimension": "O", "reverse": True, "text": "我对抽象的想法不感兴趣。"},
    {"id": "O4", "dimension": "O", "reverse": True, "text": "我的想象力不算好。"},
]

IPIP_BIG_FIVE: dict[str, Any] = {
    "id": "bigfive_ipip",
    "slug": "bigfive-ipip",
    "title": "大五人格自评（IPIP 简版）",
    "tagline": "20 题 · 看清你与世界相处的五种底色",
    "description": (
        "基于公共领域的 Mini-IPIP 量表，从外向性、宜人性、尽责性、情绪稳定性、开放性"
        "五个维度刻画你相对稳定的性格倾向。本测评仅用于自我觉察与成长参考。"
    ),
    "disclaimer": (
        "本测评由玄镜心理自评工具基于你本人的作答生成，用于自我觉察与成长参考，"
        "不构成任何医学或心理诊断；若你正处于强烈情绪困扰中，请联系专业帮助。"
    ),
    "estimatedMinutes": 3,
    "options": LIKERT_5,
    "dimensions": _DIMENSIONS,
    "items": _ITEMS,
}

SCALES: dict[str, dict[str, Any]] = {IPIP_BIG_FIVE["slug"]: IPIP_BIG_FIVE}

# ---------------------------------------------------------------------------
# 性格优势觉察（玄镜自研）：24 题 · 6 维。题目为站内原创，不采用 MBTI / Gallup
# CliftonStrengths / VIA 等需授权体系的题目与计分，规避版权风险（合规定位同上）。
# ---------------------------------------------------------------------------
_STRENGTH_DIMENSIONS: list[dict[str, Any]] = [
    {
        "key": "LR", "name": "学习力", "low_name": "专注深耕", "high_name": "好奇广博",
        "low": "你更愿意在熟悉的领域里深耕，少而精也是一条扎实的路；偶尔为生活添一点新知，会带来新鲜的能量。",
        "mid": "你对新事物保持适度的好奇，学不学、学什么，多数时候由你自己的节奏说了算。",
        "high": "你天然好奇心强、学东西快，新领域对你意味着乐趣而非负担；挑一两件真感兴趣的学透，回报最大。",
    },
    {
        "key": "CR", "name": "创造力", "low_name": "务实落地", "high_name": "点子泉涌",
        "low": "你偏好被验证过的成熟做法，稳扎稳打；你的价值在于把事情可靠地做成，而不是总去发明新轮子。",
        "mid": "你能在守成与创新之间切换：该稳的时候稳，需要新思路时也拿得出来。",
        "high": "你常能想到别人没想到的办法，脑子里的点子多到用不完；把灵感挑一个落地做成，比多想十个更值。",
    },
    {
        "key": "EM", "name": "共情力", "low_name": "边界清晰", "high_name": "善解人意",
        "low": "你不容易被他人的情绪牵着走，边界感是你的优势；你更适合用行动而非安慰去支持在意的人。",
        "mid": "你能理解别人的感受，同时也守得住自己的节奏，是朋友圈里稳稳的倾听者。",
        "high": "你天然能接住别人的情绪，是很多人愿意倾诉的对象；记得这份天赋也需要留一点给自己充电。",
    },
    {
        "key": "DR", "name": "行动力", "low_name": "谋定后动", "high_name": "说干就干",
        "low": "你想得深、动得慢，先谋定再出手；给想法设一个最小的启动动作，会让你的思考更快变成结果。",
        "mid": "你的行动张弛有度：重要的事推得动，不急的事也不勉强自己。",
        "high": "你决定了就动手，是天生的执行者；你身边很多「想得好」的计划，是靠你这种人落地的。",
    },
    {
        "key": "RS", "name": "坚韧力", "low_name": "敏感细腻", "high_name": "抗挫耐劳",
        "low": "挫折对你的触动更深，这也意味着你对自己更诚实；把大坎拆成小步，你的恢复速度会超出自己的预期。",
        "mid": "你有正常的疲惫也有不错的韧性，大多数坎熬一熬都能过去。",
        "high": "你抗压、能扛事，跌倒后恢复得快；这份韧性是你最可靠的本钱，别忘了它也值得休息。",
    },
    {
        "key": "OP", "name": "乐观力", "low_name": "风险警觉", "high_name": "积极向阳",
        "low": "你对风险更警觉，这让你少踩很多坑；你的谨慎本身也是一种优势，只是别让它挡住值得的尝试。",
        "mid": "你的心态总体平稳：该担心的会担心，但多数时候仍愿意相信事情会变好。",
        "high": "你天然倾向看到事情好的一面，是团队里的定心丸；你的乐观会真实地感染身边人。",
    },
]

_STRENGTH_ITEMS: list[dict[str, Any]] = [
    {"id": "LR1", "dimension": "LR", "reverse": False, "text": "我对新鲜事物总是充满好奇，想弄明白它背后的道理。"},
    {"id": "LR2", "dimension": "LR", "reverse": True, "text": "我对不熟悉的领域提不起兴趣。"},
    {"id": "LR3", "dimension": "LR", "reverse": False, "text": "我喜欢学习新技能，哪怕一时用不上。"},
    {"id": "LR4", "dimension": "LR", "reverse": True, "text": "学新东西让我觉得累，能躲就躲。"},
    {"id": "CR1", "dimension": "CR", "reverse": False, "text": "我常能想到别人没想到的办法。"},
    {"id": "CR2", "dimension": "CR", "reverse": True, "text": "我习惯按老办法做事，不太想创新。"},
    {"id": "CR3", "dimension": "CR", "reverse": False, "text": "我喜欢把不同的想法组合出新的可能。"},
    {"id": "CR4", "dimension": "CR", "reverse": True, "text": "面对没有先例的问题，我会觉得无从下手。"},
    {"id": "EM1", "dimension": "EM", "reverse": False, "text": "我能敏锐察觉到别人的情绪变化。"},
    {"id": "EM2", "dimension": "EM", "reverse": False, "text": "朋友遇到难事，常会找我倾诉。"},
    {"id": "EM3", "dimension": "EM", "reverse": True, "text": "我很难理解别人为什么会为小事难过。"},
    {"id": "EM4", "dimension": "EM", "reverse": False, "text": "和人相处时，我很容易站在对方角度想问题。"},
    {"id": "DR1", "dimension": "DR", "reverse": False, "text": "我决定了的事会很快动手去做。"},
    {"id": "DR2", "dimension": "DR", "reverse": True, "text": "我常常想得很多、做得很少。"},
    {"id": "DR3", "dimension": "DR", "reverse": False, "text": "任务卡住时，我会主动找办法推进。"},
    {"id": "DR4", "dimension": "DR", "reverse": True, "text": "拖延经常让我的计划不了了之。"},
    {"id": "RS1", "dimension": "RS", "reverse": False, "text": "遇到挫折后，我能比较快地恢复状态。"},
    {"id": "RS2", "dimension": "RS", "reverse": False, "text": "别人眼中的难题，我觉得是能熬过去的坎。"},
    {"id": "RS3", "dimension": "RS", "reverse": True, "text": "一次失败容易让我很长时间缓不过来。"},
    {"id": "RS4", "dimension": "RS", "reverse": False, "text": "压力再大，我也相信自己能扛住。"},
    {"id": "OP1", "dimension": "OP", "reverse": False, "text": "总体来说，我倾向期待事情往好的方向发展。"},
    {"id": "OP2", "dimension": "OP", "reverse": True, "text": "我经常担心事情会变糟。"},
    {"id": "OP3", "dimension": "OP", "reverse": False, "text": "即使进展不顺，我也相信办法总比困难多。"},
    {"id": "OP4", "dimension": "OP", "reverse": True, "text": "我很容易被坏消息影响一整天的心情。"},
]

STRENGTHS_AWARENESS: dict[str, Any] = {
    "id": "strengths_awareness",
    "slug": "strengths",
    "title": "性格优势觉察（玄镜自研）",
    "tagline": "24 题 · 看见你的六项突出优势",
    "description": (
        "从学习力、创造力、共情力、行动力、坚韧力、乐观力六个维度，"
        "帮你看见自己身上正在起作用的性格优势。本测评由玄镜自研，仅用于自我觉察与成长参考。"
    ),
    "disclaimer": (
        "本测评由玄镜自研工具基于你本人的作答生成，用于自我觉察与成长参考，"
        "不构成任何医学或心理诊断；若你正处于强烈情绪困扰中，请联系专业帮助。"
    ),
    "estimatedMinutes": 5,
    "options": LIKERT_5,
    "dimensions": _STRENGTH_DIMENSIONS,
    "items": _STRENGTH_ITEMS,
}

SCALES[STRENGTHS_AWARENESS["slug"]] = STRENGTHS_AWARENESS


def get_scale(slug: str) -> dict[str, Any] | None:
    """按 slug 取量表定义（未知返回 None）。"""
    return SCALES.get((slug or "").strip())
