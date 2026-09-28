"""量表计分引擎 —— 纯函数，不依赖数据库，便于单测与快速验证。

计分规则：
- Likert 1–5，反向题按 `6 - 作答值` 折算为正向分；
- 维度原始分 = 该维度各题（折算后）之和，再归一化到 0–100；
- 等级：<40 偏低 / 40–60 居中 / >60 偏高（相对本量表自身范围，仅作自我觉察参考）。
"""

from __future__ import annotations

from typing import Any


def _band(score: int) -> str:
    if score < 40:
        return "low"
    if score <= 60:
        return "mid"
    return "high"


def score_scale(scale: dict[str, Any], answers: dict[str, int]) -> dict[str, Any]:
    """对一份作答计分，返回维度分与整体觉察摘要。

    Args:
        scale: scale_catalog 中的量表定义（含 dimensions / items）。
        answers: {item_id: 1–5 的作答值}，缺失或越界会抛 ValueError。
    """
    items = scale["items"]
    dims = {d["key"]: d for d in scale["dimensions"]}

    # 校验作答完整性与取值
    if not answers:
        raise ValueError("作答为空")
    for it in items:
        val = answers.get(it["id"])
        if not isinstance(val, int) or val < 1 or val > 5:
            raise ValueError(f"题目 {it['id']} 作答缺失或越界（需 1–5）")

    # 逐维度累加（反向题先折算为正向分 6-answer，再归一化）
    raw: dict[str, int] = {k: 0 for k in dims}
    per_dim_count: dict[str, int] = {k: 0 for k in dims}
    for it in items:
        v = 6 - answers[it["id"]] if it["reverse"] else answers[it["id"]]
        raw[it["dimension"]] += v
        per_dim_count[it["dimension"]] += 1

    dimension_scores: list[dict[str, Any]] = []
    ranked: list[tuple[str, int]] = []
    for key, d in dims.items():
        n = per_dim_count[key]
        min_raw, max_raw = n * 1, n * 5
        normalized = round((raw[key] - min_raw) / (max_raw - min_raw) * 100)
        band = _band(normalized)
        dimension_scores.append({
            "key": key,
            "name": d["name"],
            "score": normalized,
            "band": band,
            "interpretation": d[band],
        })
        ranked.append((key, normalized))

    ranked.sort(key=lambda x: x[1], reverse=True)
    top_key, top_score = ranked[0]
    low_key, low_score = ranked[-1]
    top_name = next(d["name"] for d in dimension_scores if d["key"] == top_key)
    low_name = next(d["name"] for d in dimension_scores if d["key"] == low_key)

    summary = (
        f"在{len(dimension_scores)}个维度中，你相对更突出的是「{top_name}」（{top_score}/100），"
        f"相对更克制的是「{low_name}」（{low_score}/100）。"
        f"性格没有好坏之分，这些只是你此刻与世界相处的一种底色，"
        f"看见它，便多了一份自主选择的余地。"
    )

    return {
        "slug": scale["slug"],
        "dimensions": dimension_scores,
        "summary": summary,
        "disclaimer": scale.get("disclaimer", ""),
    }
