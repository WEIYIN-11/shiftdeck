#!/usr/bin/env python3
"""shiftdeck 視覺驗證：把 .pptx 用 LibreOffice 實際渲染成逐頁 PNG。

svg_quality_checker 只做幾何數學——抓得到溢界，抓不到「真實字型渲染後
撐出方框」。本工具補上這個缺口：用 LibreOffice（跨軟體檢查的下限基準，
它對字型度量最嚴苛）真實渲染，讓 AI 或人眼直接看圖。

    python scripts/visual_check.py <file.pptx>              # 渲染到 <file>_render/
    python scripts/visual_check.py <file.pptx> -o <dir>     # 指定輸出目錄
    python scripts/visual_check.py <file.pptx> --dpi 96     # 解析度（預設 96 = 1280x720）

管線：.pptx --LibreOffice headless--> .pdf --PyMuPDF--> 每頁一張 PNG
（LibreOffice 的 PNG 匯出只出第一頁，所以必須經過 PDF。）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SOFFICE_CANDIDATES = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    Path("/usr/bin/soffice"),
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
]


def find_soffice() -> Path:
    for p in SOFFICE_CANDIDATES:
        if p.exists():
            return p
    sys.exit("[錯誤] 找不到 LibreOffice（soffice）。視覺驗證需要它：https://www.libreoffice.org/")


def pptx_to_pdf(soffice: Path, pptx: Path, workdir: Path) -> Path:
    r = subprocess.run(
        [str(soffice), "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(pptx)],
        capture_output=True, text=True, timeout=300,
    )
    pdf = workdir / (pptx.stem + ".pdf")
    if not pdf.exists():
        sys.exit(f"[錯誤] LibreOffice 轉 PDF 失敗：\n{r.stdout}\n{r.stderr}")
    return pdf


def pdf_to_pngs(pdf: Path, outdir: Path, dpi: int) -> list[Path]:
    try:
        import fitz  # PyMuPDF —— 引擎既有依賴
    except ImportError:
        sys.exit("[錯誤] 缺 PyMuPDF：pip install PyMuPDF（安裝引擎依賴時應已包含）")

    outdir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with fitz.open(pdf) as doc:
        width = len(str(doc.page_count))
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=dpi)
            dest = outdir / f"slide_{i:0{max(width, 2)}d}.png"
            pix.save(dest)
            outputs.append(dest)
    return outputs


def main() -> None:
    ap = argparse.ArgumentParser(description="用 LibreOffice 真實渲染 .pptx 成逐頁 PNG")
    ap.add_argument("pptx", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=None)
    ap.add_argument("--dpi", type=int, default=96, help="預設 96（16:9 → 1280x720）")
    args = ap.parse_args()

    pptx = args.pptx.resolve()
    if not pptx.exists():
        sys.exit(f"[錯誤] 找不到 {pptx}")
    outdir = args.outdir or pptx.parent / f"{pptx.stem}_render"

    soffice = find_soffice()
    with tempfile.TemporaryDirectory() as td:
        pdf = pptx_to_pdf(soffice, pptx, Path(td))
        pages = pdf_to_pngs(pdf, outdir, args.dpi)

    print(f"[完成] {len(pages)} 頁 → {outdir}")
    for p in pages:
        print(f"  {p.name}")
    print("\n檢查重點：文字是否撐出方框、換行是否斷在怪異位置、元素是否重疊或貼邊。")


if __name__ == "__main__":
    main()
