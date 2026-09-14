# -*- coding: utf-8 -*-
"""P1 字段烟雾测试：打印一个真实卦例的每爻旺衰/动变深度标记与解读段落。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.paipan.liuyao import compute_liuyao

DAY = dict(year=2026, month=8, day=27)


def main() -> None:
    # 时间起卦
    r = compute_liuyao(**DAY, hour=12, question="求财问生意")
    print("=" * 70)
    print(f"本卦：{r['benGua']['name']}  变卦：{r['bianGua']['name'] if r['bianGua'] else '无'}  方式：{r['method']}")
    print("=" * 70)
    print("每爻 P1 标记：")
    for l in r["lines"]:
        flags = []
        if l.get("changsheng"):
            flags.append(f"长生[{l['changsheng']}]")
        if l.get("yuePo"):
            flags.append("月破")
        if l.get("anDong"):
            flags.append("暗动")
        if l.get("ruMu"):
            flags.append("入墓")
        if l.get("jinTui"):
            flags.append(l["jinTui"])
        if l.get("houtou"):
            flags.append(l["houtou"])
        if l.get("huaMu"):
            flags.append("化墓")
        tag = " · ".join(flags) if flags else "—"
        print(f"  {l['pos']} {l['gan']}{l['zhi']}({l['wuxing']}) {l['shishen']} "
              f"六神[{l['liushen']}] 动={l['gold']}  | {tag}")
    print("-" * 70)
    print("世爻旺衰：", r["yongshen"]["shiStrengthNote"])
    print("=" * 70)
    print("解读段落：")
    for p in r["analysis"]:
        print(f"\n【{p['title']}】\n{p['text']}")

    # 摇钱法多动爻示例
    print("\n" + "=" * 70)
    print("摇钱法多动爻示例 [0,1,2,3,0,1]（第3、4爻动）：")
    print("=" * 70)
    r2 = compute_liuyao(**DAY, hour=12, method="coin", lines_input=[0, 1, 2, 3, 0, 1], question="事业前景")
    for l in r2["lines"]:
        if l["gold"]:
            print(f"  第{l['idx']}爻 {l['gan']}{l['zhi']}({l['wuxing']}) {l['shishen']}: "
                  f"进退={l.get('jinTui') or '无'} 回头={l.get('houtou') or '无'} 化墓={l.get('huaMu')}")
    for p in r2["analysis"]:
        if p["title"] in ("动变深度", "特殊爻象"):
            print(f"\n【{p['title']}】\n{p['text']}")


if __name__ == "__main__":
    main()
