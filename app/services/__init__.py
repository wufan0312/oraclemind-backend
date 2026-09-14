"""业务逻辑层：排盘算法、AI 编排、用户服务等按模块扩展。

规划（tech_stack_plan §4）：
- services/bazi.py        八字排盘（sxtwl / lunar-python）
- services/ziwei.py       紫微斗数（安星法）
- services/liuyao.py      六爻起卦
- services/meihua.py      梅花易数
- services/qimen.py       奇门遁甲
- services/numerology.py  数字命理（原型 JS 算法移植）
- services/ai_engine.py   LLM 编排 / Prompt 模板（规划为 Node.js 侧，预留接口）
"""
