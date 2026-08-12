#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck 單頁重生成 CLI —— 只跑一頁該跑的，其餘沿用既有產物。

三種用法：

    # 1. 讀取預覽編輯器送出的重畫請求（要重畫哪一頁、換成哪個頁型）
    python overlay/regen/regen_page.py <專案> --show

    # 2. AI 重寫完那一頁的 SVG 之後，跑快路徑（單頁檢查 → 增量 finalize → 匯出）
    python overlay/regen/regen_page.py <專案> --request
    python overlay/regen/regen_page.py <專案> --page 03_kpi_6.svg

    # 3. 全量基準（量測用；行為與既有流程完全相同）
    python overlay/regen/regen_page.py <專案> --full

快路徑與全量路徑的差別只有兩處：品質檢查的第一道只驗那一頁，finalize 只重跑
那一頁。**匯出仍是全量**——引擎的釋出閘門要求 `svg_output/` 全體有一份通過的
final 品質報告，繞過它等於破壞既有流程。真正省下來的是最貴的那一段：AI 只重
畫一頁，不是整份。

Dependencies: 標準函式庫 ＋ vendor 的 ppt-master 引擎。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shiftdeck_regen as regen  # noqa: E402


def _script(name: str) -> Path:
    return regen.require_engine_scripts_dir() / name


def _run(label: str, cmd: list[str], cwd: Path) -> dict[str, Any]:
    """Run one pipeline step, timing it and capturing output."""
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    elapsed = time.perf_counter() - started
    return {
        'step': label,
        'cmd': cmd,
        'seconds': round(elapsed, 3),
        'returncode': proc.returncode,
        'stdout': proc.stdout or '',
        'stderr': proc.stderr or '',
    }


def _print_step(step: dict[str, Any], verbose: bool) -> None:
    mark = 'OK ' if step['returncode'] == 0 else 'FAIL'
    print(f"[{mark}] {step['step']}: {step['seconds']:.3f}s")
    if verbose or step['returncode'] != 0:
        for stream in ('stdout', 'stderr'):
            text = step[stream].strip()
            if text:
                print(f'  --- {stream} ---')
                for line in text.splitlines():
                    print(f'  {line}')


def _pipeline(
    project: Path,
    page: Optional[str],
    *,
    export: bool,
    verbose: bool,
) -> tuple[bool, list[dict[str, Any]]]:
    """Run the export pipeline; ``page=None`` means the full-deck baseline."""
    engine = regen.engine_root()
    if engine is None:
        raise regen.EngineUnavailable('vendor/ppt-master engine not found')
    checker = str(_script('svg_quality_checker.py'))
    finalize = str(_script('finalize_svg.py'))
    exporter = str(_script('svg_to_pptx.py'))
    steps: list[dict[str, Any]] = []

    if page is not None:
        svg_path = regen.resolve_slide(project, page)
        if svg_path is None or not svg_path.is_file():
            print(f'[錯誤] 找不到這一頁：{page}', file=sys.stderr)
            return False, steps
        steps.append(_run(
            f'單頁品質檢查 {page}',
            [sys.executable, checker, str(svg_path)],
            engine,
        ))
        _print_step(steps[-1], verbose)
        if steps[-1]['returncode'] != 0:
            return False, steps

    # The engine refuses to export unless validation/svg_quality_report.json
    # covers the *current* svg_output/ fingerprint. This is a deck-wide
    # invariant, not a per-page one — running it is cheap and skipping it
    # would mean bypassing the release gate.
    steps.append(_run(
        '全份 final 品質閘門',
        [sys.executable, checker, str(project), '--stage', 'final', '--json'],
        engine,
    ))
    _print_step(steps[-1], verbose)
    if steps[-1]['returncode'] != 0:
        return False, steps

    finalize_cmd = [sys.executable, finalize, str(project), '-q']
    if page is not None:
        finalize_cmd += ['--pages', page]
    steps.append(_run(
        '增量 finalize' if page is not None else '全量 finalize',
        finalize_cmd,
        engine,
    ))
    _print_step(steps[-1], verbose)
    if steps[-1]['returncode'] != 0:
        return False, steps

    if export:
        steps.append(_run(
            '匯出 PPTX',
            [sys.executable, exporter, str(project), '-q'],
            engine,
        ))
        _print_step(steps[-1], verbose)
        if steps[-1]['returncode'] != 0:
            return False, steps

    return True, steps


def _latest_export(project: Path) -> Optional[Path]:
    exports = project / 'exports'
    if not exports.is_dir():
        return None
    candidates = sorted(
        exports.glob('*.pptx'),
        key=lambda item: item.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _show(project: Path, as_json: bool) -> int:
    info = regen.briefing(project)
    if as_json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    if not info.get('slide'):
        print('沒有待處理的重畫請求，預覽編輯器也還沒回報選取狀態。')
        print(f"  選取狀態檔：{regen.current_path(project)}")
        print(f"  重畫請求檔：{regen.request_path(project)}")
        return 1
    origin = '預覽編輯器的重畫請求' if info['origin'] == 'request' else '預覽編輯器目前選取的頁'
    print(f'來源      {origin}')
    print(f"目標頁    {info['slide']}")
    print(f"SVG       {info['svg_path']}")
    if info.get('page_type'):
        print(f"換成頁型  {info['page_type']}")
        print(f"  契約    {info.get('contract_path')}")
        print(f"  骨架    {info.get('skeleton_path')}")
    else:
        print('換成頁型  （未指定，維持現有版面）')
    request = info.get('request') or {}
    if request.get('note'):
        print(f"使用者備註 {request['note']}")
    print(f"專案 lock {info['spec_lock']}")
    print()
    print('下一步：只重寫上面那一支 SVG，然後跑')
    if info['origin'] == 'request':
        print(f'  python overlay/regen/regen_page.py "{project}" --request')
    else:
        # No queued request — the page came from the preview's current selection,
        # so name it explicitly instead of pointing at a request that is not there.
        print(f'  python overlay/regen/regen_page.py "{project}" '
              f'--page {info["slide"]}')
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='shiftdeck 單頁重生成：只重跑那一頁該跑的步驟',
    )
    parser.add_argument('project', type=Path, help='簡報專案目錄')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--show', action='store_true',
                      help='列出待處理的重畫請求／目前選取的頁，不執行任何步驟')
    mode.add_argument('--request', action='store_true',
                      help='對 live_preview/regen_request.json 指定的那一頁跑快路徑')
    mode.add_argument('--page', type=str, default=None,
                      help='對指定的一頁跑快路徑（例：03_kpi_6.svg）')
    mode.add_argument('--full', action='store_true',
                      help='全量路徑（量測基準用，行為與既有流程相同）')
    parser.add_argument('--no-export', action='store_true',
                        help='跳過匯出 PPTX，只做檢查與 finalize')
    parser.add_argument('--json', action='store_true', help='輸出機器可讀結果')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='印出每一步的完整輸出')
    args = parser.parse_args(argv)

    project = args.project.resolve()
    if not project.is_dir():
        print(f'[錯誤] 專案目錄不存在：{project}', file=sys.stderr)
        return 1

    if args.show or not (args.request or args.page or args.full):
        return _show(project, args.json)

    page: Optional[str] = None
    request: Optional[dict[str, Any]] = None
    if args.request:
        request = regen.read_request(project)
        if not request or request.get('status') != regen.STATUS_PENDING:
            print('[錯誤] 沒有待處理的重畫請求；用 --page 指定頁面，或先在預覽裡送出請求。',
                  file=sys.stderr)
            return 1
        page = str(request.get('slide') or '')
    elif args.page:
        page = args.page

    started = time.perf_counter()
    try:
        ok, steps = _pipeline(
            project,
            page,
            export=not args.no_export,
            verbose=args.verbose,
        )
    except regen.EngineUnavailable as exc:
        print(f'[錯誤] {exc}', file=sys.stderr)
        return 1
    total = round(time.perf_counter() - started, 3)

    export_file = _latest_export(project) if not args.no_export else None
    receipt = {
        'version': 1,
        'mode': 'full' if page is None else 'single-page',
        'page': page,
        'ok': ok,
        'total_seconds': total,
        'finished_at': time.time(),
        'steps': [
            {k: v for k, v in step.items() if k not in {'stdout', 'stderr'}}
            for step in steps
        ],
        'export': str(export_file) if export_file else None,
    }
    regen.write_receipt(project, receipt)

    if ok and request is not None:
        regen.close_request(project, regen.STATUS_DONE, {
            'total_seconds': total,
            'export': str(export_file) if export_file else None,
        })

    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"\n總計 {total:.3f}s（{receipt['mode']}）")
        if export_file:
            print(f'匯出檔 {export_file}')
        if not ok:
            print('[失敗] 上面第一個 FAIL 的步驟就是原因。', file=sys.stderr)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
