#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck single-page regeneration overlay — selection channel + page types.

Single source of truth shared by two callers:

* ``overlay/regen/regen_page.py``   (CLI: the fast per-page pipeline)
* the patched ``svg_editor/server.py`` (selection channel + regeneration request)

Three responsibilities, nothing else:

1. **Selection channel** — the live preview writes "what is selected right now"
   into ``<project>/live_preview/current.json``, so a later AI turn can resolve
   "this page" / "this element" without the user retyping a filename.
2. **Page-type catalog** — reads ``overlay/pagetypes/catalog.json`` plus each
   page type's ``skeleton.svg`` (doubles as the picker thumbnail) and
   ``contract.md`` (the redraw rules the AI must follow).
3. **Regeneration request** — the preview records "redraw page X as page type Y"
   into ``<project>/live_preview/regen_request.json``; the AI reads it, rewrites
   exactly that one SVG, then runs the fast pipeline.

Like the animation overlay, this module imports fine without the engine; only
the functions that need the engine raise ``EngineUnavailable``. The patched
server therefore degrades to plain upstream behavior when ``overlay/`` is absent.

Dependencies: standard library + the vendored ppt-master engine (optional).
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

OVERLAY_DIR = Path(__file__).resolve().parent
PAGETYPES_DIR = OVERLAY_DIR.parent / 'pagetypes'
CATALOG_PATH = PAGETYPES_DIR / 'catalog.json'

#: Runtime directory the upstream live preview already owns.
LIVE_DIR_NAME = 'live_preview'
CURRENT_NAME = 'current.json'
REQUEST_NAME = 'regen_request.json'
RECEIPT_NAME = 'regen_last_run.json'
REGEN_LOG_NAME = 'regen_history.jsonl'

SVG_OUTPUT = 'svg_output'
SVG_FINAL = 'svg_final'

STATUS_PENDING = 'pending'
STATUS_DONE = 'done'
STATUS_CANCELLED = 'cancelled'

#: Page type id meaning "keep the current layout, just redraw the content".
KEEP_PAGE_TYPE = 'keep'


class EngineUnavailable(RuntimeError):
    """Raised when the vendored ppt-master engine cannot be located."""


# ---------------------------------------------------------------- engine hookup

def engine_scripts_dir() -> Optional[Path]:
    """Return the vendored engine's ``scripts`` directory, or ``None``."""
    for parent in [OVERLAY_DIR, *OVERLAY_DIR.parents]:
        candidate = (
            parent / 'vendor' / 'ppt-master' / 'skills' / 'ppt-master' / 'scripts'
        )
        if candidate.is_dir():
            return candidate
    return None


def engine_root() -> Optional[Path]:
    """Return the vendored engine repo root (the directory holding ``skills/``)."""
    scripts = engine_scripts_dir()
    return scripts.parents[2] if scripts is not None else None


def require_engine_scripts_dir() -> Path:
    scripts = engine_scripts_dir()
    if scripts is None:
        raise EngineUnavailable(
            'vendor/ppt-master engine not found; run scripts/setup.py first'
        )
    return scripts


# ---------------------------------------------------------------- page catalog

_CATALOG_CACHE: dict[str, Any] = {}


def load_catalog(force: bool = False) -> dict[str, Any]:
    """Load ``pagetypes/catalog.json``, cached on mtime so edits are picked up."""
    try:
        mtime = CATALOG_PATH.stat().st_mtime
    except OSError as exc:
        raise FileNotFoundError(f'page type catalog not found: {CATALOG_PATH}') from exc
    if not force and _CATALOG_CACHE.get('mtime') == mtime:
        return _CATALOG_CACHE['data']
    with CATALOG_PATH.open(encoding='utf-8') as handle:
        data = json.load(handle)
    _CATALOG_CACHE['mtime'] = mtime
    _CATALOG_CACHE['data'] = data
    return data


def page_types() -> list[dict[str, Any]]:
    return list(load_catalog().get('page_types', []))


def page_type_ids() -> list[str]:
    return [str(item.get('id')) for item in page_types() if item.get('id')]


def get_page_type(page_type_id: object) -> Optional[dict[str, Any]]:
    if not page_type_id:
        return None
    wanted = str(page_type_id)
    for item in page_types():
        if item.get('id') == wanted:
            return item
    return None


def page_type_dir(page_type_id: str) -> Path:
    return PAGETYPES_DIR / page_type_id


def skeleton_path(page_type_id: str) -> Path:
    return page_type_dir(page_type_id) / 'skeleton.svg'


def contract_path(page_type_id: str) -> Path:
    return page_type_dir(page_type_id) / 'contract.md'


def thumbnail_data_uri(page_type_id: str) -> Optional[str]:
    """Return ``skeleton.svg`` as a ``data:`` URI for an ``<img>`` thumbnail.

    A data URI (rather than inlining the markup) keeps the skeleton's element
    ids out of the editor's DOM — the preview canvas uses the same slot ids
    (``page-header``, ``row-1`` …) and duplicated ids would break selection.
    """
    path = skeleton_path(page_type_id)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    encoded = base64.b64encode(raw).decode('ascii')
    return f'data:image/svg+xml;base64,{encoded}'


def ui_page_types() -> list[dict[str, Any]]:
    """Return the picker payload: ids, four-language labels, and thumbnails."""
    options: list[dict[str, Any]] = []
    for item in page_types():
        page_type_id = str(item.get('id') or '')
        if not page_type_id:
            continue
        option: dict[str, Any] = {'id': page_type_id}
        for field in ('label', 'desc'):
            for lang in ('en', 'zh', 'zh_tw', 'ja'):
                key = f'{field}_{lang}'
                if item.get(key):
                    option[key] = item[key]
        if item.get('flex'):
            option['flex'] = item['flex']
        option['thumbnail'] = thumbnail_data_uri(page_type_id)
        option['has_contract'] = contract_path(page_type_id).is_file()
        options.append(option)
    return options


# ---------------------------------------------------------------- project paths

def runtime_dir(project_path: Path) -> Path:
    return Path(project_path) / LIVE_DIR_NAME


def current_path(project_path: Path) -> Path:
    return runtime_dir(project_path) / CURRENT_NAME


def request_path(project_path: Path) -> Path:
    return runtime_dir(project_path) / REQUEST_NAME


def receipt_path(project_path: Path) -> Path:
    return runtime_dir(project_path) / RECEIPT_NAME


def svg_output_dir(project_path: Path) -> Path:
    return Path(project_path) / SVG_OUTPUT


def resolve_slide(project_path: Path, name: object) -> Optional[Path]:
    """Validate one slide filename and return its path inside ``svg_output/``.

    Returns ``None`` for anything that is not a plain ``*.svg`` child of
    ``svg_output/`` — the same containment guard the upstream editor uses.
    """
    if not name:
        return None
    text = str(name)
    if '/' in text or '\\' in text or '..' in text:
        return None
    if not text.lower().endswith('.svg'):
        return None
    svg_dir = svg_output_dir(project_path)
    target = (svg_dir / text).resolve()
    try:
        target.relative_to(svg_dir.resolve())
    except ValueError:
        return None
    return target


def slide_stem(name: str) -> str:
    return str(name)[:-4] if str(name).lower().endswith('.svg') else str(name)


# ---------------------------------------------------------------- atomic JSON IO

def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write UTF-8 JSON without a BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    os.replace(tmp, path)
    return path


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        with path.open(encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def append_history(project_path: Path, record: dict[str, Any]) -> None:
    """Append one regeneration lifecycle record; never raise on IO failure."""
    try:
        target = runtime_dir(project_path)
        target.mkdir(parents=True, exist_ok=True)
        with (target / REGEN_LOG_NAME).open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    except OSError:
        pass


# ---------------------------------------------------------------- selection state

def read_current(project_path: Path) -> Optional[dict[str, Any]]:
    return _read_json(current_path(project_path))


def write_current(project_path: Path, selection: dict[str, Any]) -> dict[str, Any]:
    """Record what the preview has selected right now.

    Only whitelisted, already-validated fields are persisted; the caller is
    responsible for having checked ``slide`` against ``svg_output/``.
    """
    elements = selection.get('elements')
    if not isinstance(elements, list):
        elements = []
    slide = selection.get('slide')
    payload: dict[str, Any] = {
        'version': 1,
        'updated_at': time.time(),
        'project': str(Path(project_path).resolve()),
        'slide': str(slide) if slide else None,
        'stem': slide_stem(str(slide)) if slide else None,
        'index': selection.get('index'),
        'total': selection.get('total'),
        'element': str(selection['element']) if selection.get('element') else None,
        'elements': [str(item) for item in elements][:64],
    }
    _write_json(current_path(project_path), payload)
    return payload


# ---------------------------------------------------------------- regen request

def read_request(project_path: Path) -> Optional[dict[str, Any]]:
    return _read_json(request_path(project_path))


def write_request(
    project_path: Path,
    *,
    slide: str,
    page_type: str,
    note: str = '',
    source: str = 'live_preview',
) -> dict[str, Any]:
    """Record "redraw this page as this page type" for the next AI turn."""
    payload: dict[str, Any] = {
        'version': 1,
        'status': STATUS_PENDING,
        'requested_at': time.time(),
        'project': str(Path(project_path).resolve()),
        'slide': slide,
        'stem': slide_stem(slide),
        'page_type': page_type,
        'note': str(note or '')[:2000],
        'source': source,
        'svg_path': str(resolve_slide(project_path, slide) or ''),
        'contract_path': (
            str(contract_path(page_type)) if page_type != KEEP_PAGE_TYPE else ''
        ),
        'skeleton_path': (
            str(skeleton_path(page_type)) if page_type != KEEP_PAGE_TYPE else ''
        ),
    }
    _write_json(request_path(project_path), payload)
    append_history(project_path, dict(payload, event='requested'))
    return payload


def close_request(
    project_path: Path,
    status: str = STATUS_DONE,
    detail: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Mark the pending request finished (or cancelled) and log it."""
    current = read_request(project_path)
    if current is None:
        return None
    current['status'] = status
    current['closed_at'] = time.time()
    if detail:
        current['result'] = detail
    _write_json(request_path(project_path), current)
    append_history(project_path, dict(current, event='closed'))
    return current


def write_receipt(project_path: Path, receipt: dict[str, Any]) -> Path:
    return _write_json(receipt_path(project_path), receipt)


def read_receipt(project_path: Path) -> Optional[dict[str, Any]]:
    """Return the last pipeline run's timing receipt, if one exists."""
    return _read_json(receipt_path(project_path))


# ---------------------------------------------------------------- redraw briefing

def briefing(project_path: Path) -> dict[str, Any]:
    """Assemble everything an AI turn needs to redraw exactly one page.

    Resolution order: an explicit pending ``regen_request.json`` wins; otherwise
    fall back to whatever the preview last selected (``current.json``), so
    "redraw this page" works even when the user never touched the page picker.
    """
    project_path = Path(project_path)
    request = read_request(project_path)
    current = read_current(project_path)
    out: dict[str, Any] = {
        'project': str(project_path.resolve()),
        'request': request,
        'current': current,
        'page_types': page_type_ids(),
    }
    slide = None
    page_type = None
    if request and request.get('status') == STATUS_PENDING:
        slide = request.get('slide')
        page_type = request.get('page_type')
        out['origin'] = 'request'
    elif current:
        slide = current.get('slide')
        out['origin'] = 'current'
    else:
        out['origin'] = None

    out['slide'] = slide
    out['page_type'] = page_type
    resolved = resolve_slide(project_path, slide) if slide else None
    out['svg_path'] = str(resolved) if resolved else None
    out['svg_exists'] = bool(resolved and resolved.is_file())
    if page_type and page_type != KEEP_PAGE_TYPE:
        out['contract_path'] = str(contract_path(page_type))
        out['skeleton_path'] = str(skeleton_path(page_type))
    out['spec_lock'] = str(project_path / 'spec_lock.md')
    return out
