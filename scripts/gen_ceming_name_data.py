# -*- coding: utf-8 -*-
"""从前端 `src/data/cemingNameData.ts` 生成后端字库 `app/services/paipan/ceming_name_data.py`。

前端字库（起名用字 / 起名风格 / 诗词典籍库）是命起名算法的输入数据。
手写搬运 300+ 字条目极易出错，故用脚本从 TS 源文件直接抽取，
前端数据更新后重跑本脚本即可同步：

    .venv/Scripts/python.exe scripts/gen_ceming_name_data.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "oraclemind" / "src" / "data" / "cemingNameData.ts"
DST = ROOT / "app" / "services" / "paipan" / "ceming_name_data.py"

CHAR_RE = re.compile(
    r"\{\s*char:\s*'(?P<char>.+?)',\s*meaning:\s*'(?P<meaning>.*?)',\s*gender:\s*'(?P<gender>.+?)'\s*\}"
)
STYLE_RE = re.compile(
    r"\{\s*key:\s*'(?P<key>.+?)',\s*label:\s*'(?P<label>.*?)',\s*desc:\s*'(?P<desc>.*?)',"
    r"\s*preferElements:\s*\[(?P<els>.*?)\]\s*\}"
)
POETRY_RE = re.compile(
    r"\{\s*source:\s*'(?P<source>.+?)',\s*quote:\s*'(?P<quote>.*?)',\s*title:\s*'(?P<title>.*?)',"
    r"\s*author:\s*'(?P<author>.*?)',\s*chars:\s*\[(?P<chars>.*?)\],\s*meaning:\s*'(?P<meaning>.*?)',"
    r"\s*gender:\s*'(?P<gender>.+?)'\s*\}"
)
EL_RE = re.compile(r"^\s{2}([金木水火土]):\s*\[", re.M)


def _section(text: str, name: str) -> str:
    """截取 `export const NAME: ... = {` / `= [` 起到其后的首个顶层 `};` / `];`。"""
    m = re.search(rf"export const {name}\b.*?=\s*([\{{\[])", text)
    if not m:
        raise SystemExit(f"未找到 {name} 定义")
    start = m.end()
    end = text.find("\n]" if m.group(1) == "[" else "\n};", start)
    if end < 0:
        raise SystemExit(f"{name} 段落未闭合")
    return text[start:end]


def _py(s: str) -> str:
    """转成 Python 单引号字符串（内容里没有单引号，见源文件）。"""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"找不到前端数据文件：{SRC}")
    text = SRC.read_text(encoding="utf-8")

    # ---- 起名用字库 ----
    sec = _section(text, "NAME_CHARS")
    marks = [(m.start(), m.group(1)) for m in EL_RE.finditer(sec)]
    if len(marks) != 5:
        raise SystemExit(f"NAME_CHARS 应有 5 个五行分组，实际 {len(marks)}")
    marks.append((len(sec), None))
    char_rows: list[str] = []
    total = 0
    for i in range(5):
        el = marks[i][1]
        chunk = sec[marks[i][0]:marks[i + 1][0]]
        char_rows.append(f"    {_py(el)}: [")
        for m in CHAR_RE.finditer(chunk):
            char_rows.append(
                "        {'char': %s, 'meaning': %s, 'gender': %s},"
                % (_py(m.group("char")), _py(m.group("meaning")), _py(m.group("gender")))
            )
            total += 1
        char_rows.append("    ],")

    # ---- 起名风格 ----
    style_rows: list[str] = []
    for m in STYLE_RE.finditer(_section(text, "NAME_STYLES")):
        els = ", ".join(_py(x.strip().strip("'")) for x in m.group("els").split(",") if x.strip())
        style_rows.append(
            "    {'key': %s, 'label': %s, 'desc': %s, 'preferElements': [%s]},"
            % (_py(m.group("key")), _py(m.group("label")), _py(m.group("desc")), els)
        )
    if len(style_rows) != 7:
        raise SystemExit(f"NAME_STYLES 应有 7 条，实际 {len(style_rows)}")

    # ---- 诗词典籍起名库 ----
    poetry_rows: list[str] = []
    for m in POETRY_RE.finditer(_section(text, "POETRY_LIB")):
        chars = ", ".join(_py(x.strip().strip("'")) for x in m.group("chars").split(",") if x.strip())
        poetry_rows.append(
            "    {'source': %s, 'quote': %s, 'title': %s, 'author': %s, 'chars': [%s],"
            " 'meaning': %s, 'gender': %s},"
            % (
                _py(m.group("source")),
                _py(m.group("quote")),
                _py(m.group("title")),
                _py(m.group("author")),
                chars,
                _py(m.group("meaning")),
                _py(m.group("gender")),
            )
        )
    if not poetry_rows:
        raise SystemExit("POETRY_LIB 抽取为空")

    out = [
        '"""起名用字库 / 起名风格 / 诗词典籍库 —— 由 scripts/gen_ceming_name_data.py 从前端生成。',
        "",
        "源：`oraclemind/src/data/cemingNameData.ts`（NAME_CHARS / NAME_STYLES / POETRY_LIB）。",
        "**不要手工编辑本文件**；前端数据更新后重跑生成脚本即可同步。",
        f"当前：字库 {total} 条，风格 {len(style_rows)} 条，诗词 {len(poetry_rows)} 条。",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# 五行遍历顺序与前端 FIVE_ELEMENTS 一致：金木水火土（影响候选池顺序，不可调换）",
        "NAME_CHARS: dict[str, list[dict[str, str]]] = {",
        *char_rows,
        "}",
        "",
        "NAME_STYLES: list[dict] = [",
        *style_rows,
        "]",
        "",
        "POETRY_LIB: list[dict] = [",
        *poetry_rows,
        "]",
        "",
    ]
    DST.write_text("\n".join(out), encoding="utf-8")
    print(f"已生成 {DST}（字库 {total} / 风格 {len(style_rows)} / 诗词 {len(poetry_rows)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
