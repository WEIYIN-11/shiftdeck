#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Expand a shiftdeck deck-animation preset into ``<project>/animations.json``.

The confirmation page writes the deck-level ``defaults`` block as soon as the
user picks a preset — at that moment ``svg_output/`` does not exist yet. Run this
after the pages are authored to expand the same preset into explicit per-slide,
per-group Animation Pane rows using the project's real ``<g id>`` anchors.

Usage:
    python overlay/animations/apply_preset.py <project> --preset lively
    python overlay/animations/apply_preset.py <project> --from-result
    python overlay/animations/apply_preset.py <project> --preset minimal --defaults-only
    python overlay/animations/apply_preset.py --list

Examples:
    python overlay/animations/apply_preset.py projects/demo --from-result
    python overlay/animations/apply_preset.py projects/demo --preset professional --replace

Dependencies:
    Standard library + the vendored ppt-master engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shiftdeck_animations as sda  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Write animations.json from a shiftdeck deck-animation preset.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('project_path', nargs='?', help='Project directory')
    parser.add_argument(
        '--preset',
        help=f'Preset id, or "{sda.NO_PRESET}" to write nothing',
    )
    parser.add_argument(
        '--from-result',
        action='store_true',
        help='Read the preset chosen on the confirmation page (confirm_ui/result.json)',
    )
    parser.add_argument(
        '--defaults-only',
        action='store_true',
        help='Write only the deck-level defaults block (no per-group rows)',
    )
    parser.add_argument(
        '--replace',
        action='store_true',
        help='Discard existing per-slide entries instead of merging over them',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        dest='list_presets',
        help='Print the available presets and exit',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_presets:
        for preset in sda.presets():
            print(f"{preset['id']:<14} {preset.get('label_zh_tw', '')} — "
                  f"{preset.get('label_en', '')}")
        print(f"{sda.NO_PRESET:<14} 不設定（維持引擎預設：fade 轉場、頁內 none）")
        return 0

    if not args.project_path:
        print('Error: project_path is required', file=sys.stderr)
        return 2
    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f'Error: Project path does not exist: {project_path}', file=sys.stderr)
        return 1

    preset_id = args.preset
    if args.from_result and not preset_id:
        preset_id = sda.selected_preset_id(project_path)
        if preset_id is None:
            print('No deck animation preset was chosen on the confirmation page; '
                  'nothing written.')
            return 0
    if not preset_id:
        print('Error: pass --preset <id> or --from-result', file=sys.stderr)
        return 2

    if preset_id == sda.NO_PRESET:
        print('Preset "none": nothing written, engine defaults keep applying.')
        return 0

    try:
        path, errors = sda.apply_preset(
            project_path,
            preset_id,
            defaults_only=args.defaults_only,
            keep_slides=not args.replace,
        )
    except (sda.EngineUnavailable, FileNotFoundError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f'Error: {error}', file=sys.stderr)
        return 1
    if path is None:
        print('Nothing written.')
        return 0

    config = json.loads(path.read_text(encoding='utf-8'))
    slides = config.get('slides') or {}
    rows = sum(
        len((group or {}).get('effects') or [])
        for slide in slides.values()
        for group in (slide.get('groups') or {}).values()
    )
    print(f'animations.json written: {path}')
    print(f'preset={preset_id} slides={len(slides)} animation_rows={rows}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
