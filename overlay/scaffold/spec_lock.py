#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck 版的 spec_lock 產生器 —— 把頁型庫真的會用到的欄位一次補齊。

    python overlay/scaffold/spec_lock.py <專案路徑>
    python overlay/scaffold/spec_lock.py <專案路徑> --force   # 覆蓋既有檔案

**為什麼需要這支**：引擎的 `project_manager.py scaffold-lock` 給的是引擎通用的
最小集合——`typography` 只有 `body` 與 `title`、`colors` 只有四個鍵。那對上游是
對的，它不知道 shiftdeck 加了頁型庫。但頁型的骨架實際用到五個字級與八個色角色，
於是照著 scaffold 填完必定撞上：

    undeclared font-size 24 (8 occurrences) exceeds the sparse-display limit of 2

四個獨立的測試都踩了同一個坑（2026-08-15）。這支腳本補的就是那段落差：先讓引擎
產生基底（schema 跟著上游走，不分叉），再把頁型庫真正需要的欄位填進去。

**字級與顏色不是寫死的**——每次執行都重新掃 `overlay/pagetypes/*/skeleton.svg`，
所以新增頁型時自動跟上，不必回來改這支腳本。這呼應頁型庫本來的設計：新增一個
頁型＝一個資料夾＋`catalog.json` 一筆，不必改程式碼。

**誠實的邊界**：這支只補「機器推得出來的」欄位。`communication`、`mode`、
`visual_style` 那些要靠人或 AI 判斷的仍然是 `[fill]`，執行完會列出還剩哪些。

Dependencies: 只有標準函式庫 ＋ vendor 的引擎（用來產生基底）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGETYPES = REPO / "overlay" / "pagetypes"
ENGINE_CLI = (REPO / "vendor" / "ppt-master" / "skills" / "ppt-master"
              / "scripts" / "project_manager.py")

# 依骨架實際用途命名。掃出來的字級由大到小對應這串；多出來的會以 extra_<size> 命名。
SIZE_ROLES = ["metric", "title", "subtitle", "body", "annotation"]

# 骨架用的中性色 → 語意角色。這些是可直接用的預設值，不是佔位符；
# 想換配色改右邊的十六進位碼即可，角色名要保留（契約的換色表按角色走）。
COLOR_ROLES = [
    ("bg", "#FFFFFF", "頁底"),
    ("secondary_bg", "#F4F5F7", "次級區塊、卡片底"),
    ("primary", "#1F2430", "主標與正文"),
    ("accent", "#4A5568", "強調短棒、進度實績、重點色塊"),
    ("body_text", "#5A6270", "次級說明文字"),
    ("muted", "#9AA1AC", "註記、來源、眉標"),
    ("border", "#D0D4DA", "卡片與格線描邊"),
    ("track", "#E8EAED", "進度條軌道等未填滿的底"),
    ("text", "#1F2430", "引擎必要鍵，與 primary 同值即可"),
]


def scan_skeleton_sizes() -> list[int]:
    sizes: set[int] = set()
    for skeleton in sorted(PAGETYPES.glob("*/skeleton.svg")):
        text = skeleton.read_text(encoding="utf-8")
        sizes.update(int(m) for m in re.findall(r'font-size="(\d+)"', text))
    return sorted(sizes, reverse=True)


def render_typography(sizes: list[int]) -> list[str]:
    rows = [
        "## typography",
        "- font_family: Microsoft JhengHei",
        "- title_family: Microsoft JhengHei",
        "- body_family: Microsoft JhengHei",
    ]
    for i, size in enumerate(sizes):
        role = SIZE_ROLES[i] if i < len(SIZE_ROLES) else f"extra_{size}"
        rows.append(f"- {role}: {size}")
    rows.append("")
    return rows


def render_colors() -> list[str]:
    # 不要在值後面加行內註解：引擎的 load_theme_color_spec 會把整段當色碼丟給
    # parse_hex_color，一個註解就讓那一行被靜默跳過；全部跳過的話 roles 變空，
    # 品質閘門會回報「theme contract is missing: colors」。角色說明放輸出訊息裡。
    rows = ["## colors"]
    rows += [f"- {name}: {value}" for name, value, _ in COLOR_ROLES]
    rows.append("")
    return rows


def render_page_rhythm(project: Path) -> list[str]:
    svgs = sorted((project / "svg_output").glob("*.svg"))
    rows = ["## page_rhythm"]
    if not svgs:
        rows.append("- P01: [fill]　# svg_output/ 還是空的，畫完可以再跑一次這支補齊")
    else:
        for i, svg in enumerate(svgs, 1):
            rows.append(f"- P{i:02d}: [fill]（{svg.name}）")
    rows.append("")
    return rows


def replace_section(lines: list[str], header: str, new_rows: list[str]) -> list[str]:
    """用 new_rows 換掉某個 `## 區塊`，找不到就附加在結尾。"""
    out, i, replaced = [], 0, False
    while i < len(lines):
        if lines[i].strip() == header:
            out.extend(new_rows)
            replaced = True
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    if not replaced:
        out.extend(new_rows)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="產生已補齊頁型庫欄位的 spec_lock.md")
    parser.add_argument("project_path")
    parser.add_argument("--force", action="store_true", help="覆蓋既有的 spec_lock.md")
    args = parser.parse_args()

    project = Path(args.project_path)
    if not project.is_dir():
        print(f"找不到專案資料夾：{project}", file=sys.stderr)
        return 1

    lock = project / "spec_lock.md"
    if lock.exists() and not args.force:
        print(f"{lock} 已經存在。要重新產生請加 --force（會蓋掉現有內容）")
        return 1

    if lock.exists():
        lock.unlink()

    # 先讓引擎產生基底，schema 跟著上游走
    result = subprocess.run(
        [sys.executable, str(ENGINE_CLI), "scaffold-lock", str(project)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not lock.exists():
        print("引擎的 scaffold-lock 失敗：", file=sys.stderr)
        print(result.stdout or result.stderr, file=sys.stderr)
        return result.returncode or 1

    sizes = scan_skeleton_sizes()
    lines = lock.read_text(encoding="utf-8").splitlines()
    lines = replace_section(lines, "## typography", render_typography(sizes))
    lines = replace_section(lines, "## colors", render_colors())
    lines = replace_section(lines, "## page_rhythm", render_page_rhythm(project))
    lock.write_text("\n".join(lines) + "\n", encoding="utf-8")

    remaining = [ln for ln in lines if "[fill]" in ln]
    print(f"[OK] 已產生 {lock}")
    print(f"     字級 {len(sizes)} 個（掃自 {len(list(PAGETYPES.glob('*/skeleton.svg')))} 個頁型骨架）："
          f"{'、'.join(str(s) for s in sizes)}")
    print(f"     色角色 {len(COLOR_ROLES)} 個，已填中性預設值，可直接用也可改")
    if remaining:
        print(f"\n還有 {len(remaining)} 行要你或 AI 判斷後填：")
        for ln in remaining:
            print(f"     {ln.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
