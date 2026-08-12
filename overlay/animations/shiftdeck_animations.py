#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck animation overlay — deck presets, element menu, animations.json IO.

This module is the single source of truth shared by three callers:

* ``overlay/animations/apply_preset.py`` (CLI)
* the patched ``confirm_ui/server.py``  (writes deck defaults at Stage 2 confirm)
* the patched ``svg_editor/server.py``  (element-level tuning in the preview)

It never redefines an animation effect. Every effect key referenced by
``presets.json`` is validated against the engine's own machine-readable registry
(``pptx_animation_presets.json``, 203 effects) and every config it writes is
validated with the engine's own ``animations.json`` validators before it lands
on disk. If the engine cannot be located the module still imports; callers get
``EngineUnavailable`` from the functions that need it, so the patched servers can
degrade to plain upstream behavior instead of crashing.

Dependencies: standard library + the vendored ppt-master engine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

OVERLAY_DIR = Path(__file__).resolve().parent
PRESETS_PATH = OVERLAY_DIR / 'presets.json'

CONFIG_NAME = 'animations.json'
CONFIRM_RESULT_REL = Path('confirm_ui') / 'result.json'

#: Sentinel meaning "the user did not choose a deck animation preset".
#: Nothing is written for it, so behavior stays byte-identical to upstream.
NO_PRESET = 'none'

DEFAULT_ELEMENT_CLASS = 'default'
DEFAULT_PAGE_ROLE = 'content'


class EngineUnavailable(RuntimeError):
    """Raised when the vendored ppt-master engine cannot be imported."""


# ---------------------------------------------------------------- engine hookup

def engine_scripts_dir() -> Optional[Path]:
    """Return the vendored engine's ``scripts`` directory, or ``None``.

    Walks up from this file looking for the vendored engine. When this module is
    imported *by* the engine the directory is already on ``sys.path``; the walk
    still runs so the CLI works standalone.
    """
    for parent in [OVERLAY_DIR, *OVERLAY_DIR.parents]:
        candidate = (
            parent / 'vendor' / 'ppt-master' / 'skills' / 'ppt-master' / 'scripts'
        )
        if candidate.is_dir():
            return candidate
    return None


def ensure_engine_importable() -> None:
    """Put the engine's ``scripts`` directory on ``sys.path`` exactly once."""
    try:
        import pptx_animations  # noqa: F401
        return
    except ImportError:
        pass
    scripts_dir = engine_scripts_dir()
    if scripts_dir is None:
        raise EngineUnavailable(
            'vendor/ppt-master engine not found; run scripts/setup.py first'
        )
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import pptx_animations  # noqa: F401
    except ImportError as exc:  # pragma: no cover - defensive
        raise EngineUnavailable(f'cannot import the engine: {exc}') from exc


def _registry() -> dict[str, dict[str, Any]]:
    """Return the engine's 203-effect registry keyed by canonical effect key."""
    scripts_dir = engine_scripts_dir()
    if scripts_dir is None:
        raise EngineUnavailable('vendor/ppt-master engine not found')
    path = scripts_dir / 'pptx_animation_presets.json'
    with path.open(encoding='utf-8') as handle:
        data = json.load(handle)
    return {entry['key']: entry for entry in data.get('effects', [])}


# ---------------------------------------------------------------- preset catalog

_CATALOG_CACHE: dict[str, Any] = {}


def load_catalog(force: bool = False) -> dict[str, Any]:
    """Load ``presets.json``, caching on mtime so a live server picks up edits."""
    try:
        mtime = PRESETS_PATH.stat().st_mtime
    except OSError as exc:
        raise FileNotFoundError(f'animation presets not found: {PRESETS_PATH}') from exc
    if not force and _CATALOG_CACHE.get('mtime') == mtime:
        return _CATALOG_CACHE['data']
    with PRESETS_PATH.open(encoding='utf-8') as handle:
        data = json.load(handle)
    _CATALOG_CACHE['mtime'] = mtime
    _CATALOG_CACHE['data'] = data
    return data


def presets() -> list[dict[str, Any]]:
    return list(load_catalog().get('presets', []))


def get_preset(preset_id: object) -> Optional[dict[str, Any]]:
    """Return one preset definition, or ``None`` for unknown/``none``."""
    if not preset_id or str(preset_id) == NO_PRESET:
        return None
    for preset in presets():
        if preset.get('id') == str(preset_id):
            return preset
    return None


def preset_ids() -> list[str]:
    return [str(preset.get('id')) for preset in presets() if preset.get('id')]


def ui_presets() -> list[dict[str, Any]]:
    """Return the confirm-page option list: ids plus localized label/desc."""
    options = []
    for preset in presets():
        option = {'id': preset.get('id')}
        for field in ('label', 'desc'):
            for lang in ('en', 'zh', 'zh_tw', 'ja'):
                key = f'{field}_{lang}'
                if preset.get(key):
                    option[key] = preset[key]
        options.append(option)
    return options


# ---------------------------------------------------------------- classification

def _match_id(value: str, rules: Iterable[dict[str, Any]], fallback: str) -> str:
    lowered = str(value or '').lower()
    for rule in rules:
        for needle in rule.get('match', ()):
            if str(needle).lower() in lowered:
                return str(rule.get('id'))
    return fallback


def classify_group(group_id: str) -> str:
    """Map one top-level ``<g id>`` to a preset element class."""
    return _match_id(
        group_id,
        load_catalog().get('element_classes', []),
        DEFAULT_ELEMENT_CLASS,
    )


def classify_slide(slide_stem: str) -> str:
    """Map one SVG stem (``03_kpi_6``) to a preset page role."""
    return _match_id(
        slide_stem,
        load_catalog().get('page_roles', []),
        DEFAULT_PAGE_ROLE,
    )


# ---------------------------------------------------------------- effect menu

def effect_menu() -> dict[str, Any]:
    """Build the curated element menu from the engine registry.

    The curation list (which 6-8 effects per category) lives in ``presets.json``;
    every other field — display name, native default duration, and the exact
    ``effect_options`` contract — is read from the engine so the menu can never
    drift from what the exporter actually accepts.
    """
    ensure_engine_importable()
    from pptx_animations import describe_animation_effect  # noqa: WPS433

    registry = _registry()
    totals: dict[str, int] = {}
    for entry in registry.values():
        category = entry.get('category', '')
        totals[category] = totals.get(category, 0) + 1

    catalog = load_catalog()
    menu = catalog.get('menu', {})
    out: dict[str, Any] = {
        'categories': [],
        'totals': totals,
        'option_labels': catalog.get('option_labels', {}),
        'seed_options': catalog.get('seed_options', {}),
    }
    for category in ('entrance', 'emphasis', 'path', 'exit'):
        rows = []
        for item in menu.get(category, []):
            key = item.get('key')
            entry = registry.get(key)
            if entry is None:
                raise ValueError(
                    f'presets.json menu references an unknown effect: {key}'
                )
            described = describe_animation_effect(key)
            row = dict(item)
            row['name'] = entry.get('name')
            row['category'] = entry.get('category')
            row['default_duration'] = round(
                float(entry.get('default_duration_ms') or 500) / 1000.0, 3
            )
            row['duration_scalable'] = bool(entry.get('duration_scalable', True))
            row['options'] = described.get('effect_options') or {}
            rows.append(row)
        out['categories'].append({
            'id': category,
            'curated': len(rows),
            'total': totals.get(category, 0),
            'effects': rows,
        })
    return out


# ---------------------------------------------------------------- config building

def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def defaults_config(preset: dict[str, Any]) -> dict[str, Any]:
    """Return the deck-level-only sidecar for one preset.

    Written at Stage 2 confirm, when ``svg_output/`` does not exist yet. It is a
    complete, valid ``animations.json`` on its own: unlisted slides inherit
    ``defaults``.
    """
    return {
        'version': 1,
        'defaults': _clone(preset.get('defaults', {})),
    }


def _slide_targets(project_path: Path) -> dict[str, list]:
    ensure_engine_importable()
    from svg_to_pptx.animation_config import scan_project_targets  # noqa: WPS433

    targets_by_slide, _anonymous = scan_project_targets(Path(project_path))
    return targets_by_slide


def full_config(
    project_path: Path,
    preset: dict[str, Any],
    *,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Expand one preset against the project's real SVG anchors.

    Every animated group is written explicitly, so the sidecar stays readable and
    the exporter never has to guess. ``defaults.animation.effect`` stays ``none``
    — only groups this function lists get Animation Pane rows.
    """
    config = defaults_config(preset)
    role_overrides = preset.get('page_roles', {}) or {}
    element_rules = preset.get('elements', {}) or {}

    slides: dict[str, Any] = {}
    for slide_stem, targets in _slide_targets(project_path).items():
        slide_cfg: dict[str, Any] = {}
        role = classify_slide(slide_stem)
        role_cfg = role_overrides.get(role) or {}
        if role_cfg.get('transition'):
            slide_cfg['transition'] = _clone(role_cfg['transition'])
        if role_cfg.get('animation'):
            slide_cfg['animation'] = _clone(role_cfg['animation'])

        groups: dict[str, Any] = {}
        order = 0
        for target in targets:
            if getattr(target, 'chrome', False):
                continue
            if getattr(target, 'structurally_static', False):
                continue
            rule = element_rules.get(classify_group(target.group_id))
            if rule is None:
                rule = element_rules.get(DEFAULT_ELEMENT_CLASS)
            if not rule or not rule.get('effects'):
                continue
            order += 1
            rows = []
            for row in _clone(rule['effects']):
                # One order value per group: ties keep SVG group order and then
                # array order, so a group's own rows stay in authored sequence.
                row['order'] = order
                rows.append(row)
            groups[target.group_id] = {'effects': rows}
        if groups:
            slide_cfg['groups'] = groups
        if slide_cfg:
            slides[slide_stem] = slide_cfg

    if slides:
        config['slides'] = slides
    if existing:
        merged_slides = _clone(existing.get('slides') or {})
        merged_slides.update(config.get('slides') or {})
        if merged_slides:
            config['slides'] = merged_slides
    return config


def merge_defaults(existing: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    """Replace only the ``defaults`` block, preserving hand-tuned ``slides``."""
    merged = _clone(existing) if existing else {'version': 1}
    merged['version'] = 1
    merged['defaults'] = _clone(preset.get('defaults', {}))
    return merged


# ---------------------------------------------------------------- config IO

def config_path(project_path: Path) -> Path:
    return Path(project_path) / CONFIG_NAME


def read_config(project_path: Path) -> Optional[dict[str, Any]]:
    path = config_path(project_path)
    if not path.exists():
        return None
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def validate_config(project_path: Path, config: dict[str, Any]) -> list[str]:
    """Return the engine's own fatal errors for one candidate config.

    Reference checks (missing slide/group) only run once ``svg_output/`` exists;
    a Stage-2 defaults-only sidecar is validated for shape alone.
    """
    ensure_engine_importable()
    from svg_to_pptx.animation_config import (  # noqa: WPS433
        validate_animation_config,
        validate_animation_config_errors,
        validate_transition_config,
    )

    errors = list(dict.fromkeys(
        validate_transition_config(config)
        + validate_animation_config_errors(config)
    ))
    if errors:
        return errors
    svg_dir = Path(project_path) / 'svg_output'
    if not svg_dir.is_dir() or not any(svg_dir.glob('*.svg')):
        return []
    messages = validate_animation_config(Path(project_path), config)
    return [
        message for message in messages
        if ' has no id and cannot be customized in animations.json' not in message
    ]


def write_config(project_path: Path, config: dict[str, Any]) -> Path:
    """Atomically write ``<project>/animations.json`` as UTF-8 without BOM."""
    path = config_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    os.replace(tmp, path)
    return path


def selected_preset_id(project_path: Path) -> Optional[str]:
    """Return the preset id the confirmation page recorded, if any."""
    result_file = Path(project_path) / CONFIRM_RESULT_REL
    try:
        with result_file.open(encoding='utf-8') as handle:
            result = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(result, dict):
        return None
    deck_animation = result.get('deck_animation')
    if isinstance(deck_animation, dict):
        value = deck_animation.get('preset')
    else:
        value = deck_animation
    if not value or str(value) == NO_PRESET:
        return None
    return str(value)


def apply_preset(
    project_path: Path,
    preset_id: str,
    *,
    defaults_only: bool = False,
    keep_slides: bool = True,
) -> tuple[Optional[Path], list[str]]:
    """Write the sidecar for ``preset_id``. Returns ``(path, errors)``.

    ``preset_id == 'none'`` writes nothing and removes nothing: a deck with no
    chosen preset must behave exactly as it did before this overlay existed.
    """
    if not preset_id or preset_id == NO_PRESET:
        return None, []
    preset = get_preset(preset_id)
    if preset is None:
        return None, [f'unknown animation preset: {preset_id}']

    existing = read_config(project_path)
    if defaults_only:
        config = (
            merge_defaults(existing, preset) if existing else defaults_config(preset)
        )
    else:
        config = full_config(
            project_path,
            preset,
            existing=existing if keep_slides else None,
        )
    errors = validate_config(project_path, config)
    if errors:
        return None, errors
    return write_config(project_path, config), []
