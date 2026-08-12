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
import re
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


USER_PRESETS_DIR = OVERLAY_DIR / 'user'


def user_presets() -> list[dict[str, Any]]:
    """Load ``overlay/animations/user/*.json`` — one preset object per file.

    Deliberately not cached: these are hand-edited far more often than the
    built-ins, and reading four small files costs nothing next to an export.
    A malformed file is skipped rather than taking the whole catalog down; the
    built-in presets must never become unreachable because of a user's typo.
    """
    if not USER_PRESETS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(USER_PRESETS_DIR.glob('*.json')):
        try:
            with path.open(encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not data.get('id'):
            continue
        data['source'] = 'user'
        data['path'] = str(path)
        out.append(data)
    return out


def presets() -> list[dict[str, Any]]:
    """Return the built-in presets plus the user's own, built-ins winning ties."""
    builtin = list(load_catalog().get('presets', []))
    known = {str(item.get('id')) for item in builtin}
    return builtin + [
        item for item in user_presets() if str(item.get('id')) not in known
    ]


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
        if preset.get('source') == 'user':
            option['source'] = 'user'
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


def _rotate_variant(rule: dict[str, Any], variant: Any) -> list[dict[str, Any]]:
    """Resolve one ``rotate`` entry into a concrete list of effect rows.

    Two accepted shapes, because both are natural to write by hand:
    a bare effect key (``"entrance_wipe"``) reuses the rule's own first row with
    that effect substituted, and a full row array spells everything out.
    Substituting an effect key drops the previous ``effect_options`` — options
    are effect-specific, and carrying them across would fail engine validation.
    """
    if isinstance(variant, list):
        return _clone(variant)
    if isinstance(variant, str):
        base = _clone(rule.get('effects') or [{}]) or [{}]
        row = base[0]
        row['effect'] = variant
        seeds = load_catalog().get('seed_options', {}) or {}
        if seeds.get(variant):
            row['effect_options'] = _clone(seeds[variant])
        else:
            row.pop('effect_options', None)
        return base
    return _clone(rule.get('effects') or [])


def _element_rows(
    rule: dict[str, Any],
    index: int,
    peers: int,
) -> list[dict[str, Any]]:
    """Return one element's effect rows, applying optional rotation and ramping.

    ``effects``     the plain form every built-in preset uses.
    ``rotate``      alternatives that peers of the same class take turns through,
                    so four cards on one page stop playing the identical move.
    ``progressive`` per-field numeric ramps such as ``{"duration": [0.45, 0.3]}``:
                    the first peer gets 0.45, the last 0.3, the rest evenly
                    spaced. Applied after rotation.

    Both extras are opt-in. A rule carrying neither returns ``effects`` verbatim,
    which is why the three built-in presets keep byte-identical output.
    """
    variants = rule.get('rotate')
    if isinstance(variants, list) and variants:
        rows = _rotate_variant(rule, variants[index % len(variants)])
    else:
        rows = _clone(rule.get('effects') or [])
    if not isinstance(rows, list) or not rows:
        return []

    ramp = rule.get('progressive')
    if isinstance(ramp, dict) and ramp:
        span = max(peers - 1, 1)
        ratio = min(index, span) / span
        for field, bounds in ramp.items():
            if not isinstance(bounds, list) or len(bounds) != 2:
                continue
            try:
                start = float(bounds[0])
                end = float(bounds[1])
            except (TypeError, ValueError):
                continue
            value = round(start + (end - start) * ratio, 3)
            for row in rows:
                row[field] = value
    return rows


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

        # Two passes: peers of the same element class must know how many of
        # them share the page before rotation or ramping can be assigned.
        animated: list[tuple[Any, str, dict[str, Any]]] = []
        for target in targets:
            if getattr(target, 'chrome', False):
                continue
            if getattr(target, 'structurally_static', False):
                continue
            class_id = classify_group(target.group_id)
            rule = element_rules.get(class_id)
            if rule is None:
                class_id = DEFAULT_ELEMENT_CLASS
                rule = element_rules.get(DEFAULT_ELEMENT_CLASS)
            if not rule or not (rule.get('effects') or rule.get('rotate')):
                continue
            animated.append((target, class_id, rule))

        peer_counts: dict[str, int] = {}
        for _target, class_id, _rule in animated:
            peer_counts[class_id] = peer_counts.get(class_id, 0) + 1

        groups: dict[str, Any] = {}
        seen: dict[str, int] = {}
        order = 0
        for target, class_id, rule in animated:
            index = seen.get(class_id, 0)
            seen[class_id] = index + 1
            rows = _element_rows(rule, index, peer_counts[class_id])
            if not rows:
                continue
            order += 1
            for row in rows:
                # One order value per group: ties keep SVG group order and then
                # array order, so a group's own rows stay in authored sequence.
                row['order'] = order
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


USER_PRESET_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,39}$')


def derive_preset(
    project_path: Path,
    preset_id: str,
    *,
    labels: Optional[dict[str, str]] = None,
    base_preset_id: Optional[str] = None,
) -> dict[str, Any]:
    """Turn a project's tuned ``animations.json`` back into a reusable preset.

    The sidecar is concrete (this page, this ``<g id>``); a preset is abstract
    (this *kind* of element). The bridge is the same ``element_classes`` /
    ``page_roles`` matcher used to expand a preset in the first place: each
    group id is classified, and the first group seen for a class supplies that
    class's rows. Round-tripping an unmodified preset therefore reproduces it.

    Raises ``ValueError`` for a bad id or a project with nothing to learn from.
    """
    if not USER_PRESET_ID_RE.match(str(preset_id or '')):
        raise ValueError(
            'preset id must be lowercase letters, digits, "-" or "_" '
            '(max 40 characters)'
        )
    if preset_id in {str(item.get('id')) for item in load_catalog().get('presets', [])}:
        raise ValueError(f'"{preset_id}" is a built-in preset id; choose another')

    config = read_config(project_path)
    if not config:
        raise ValueError('this project has no animations.json to derive from')
    slides = config.get('slides') or {}
    if not slides:
        raise ValueError(
            'animations.json has no per-page settings yet; apply a preset or '
            'tune some elements first'
        )

    base = get_preset(base_preset_id) or {}
    elements: dict[str, Any] = {}
    page_roles: dict[str, Any] = {}
    for slide_stem, slide_cfg in slides.items():
        role = classify_slide(slide_stem)
        role_cfg = page_roles.setdefault(role, {})
        for field in ('transition', 'animation'):
            if slide_cfg.get(field) and field not in role_cfg:
                role_cfg[field] = _clone(slide_cfg[field])
        for group_id, block in (slide_cfg.get('groups') or {}).items():
            class_id = classify_group(group_id)
            if class_id in elements:
                continue
            rows = block.get('effects') if isinstance(block, dict) else None
            if not isinstance(rows, list) or not rows:
                continue
            cleaned = []
            for row in _clone(rows):
                row.pop('order', None)
                cleaned.append(row)
            elements[class_id] = {'effects': cleaned}

    page_roles = {role: cfg for role, cfg in page_roles.items() if cfg}
    preset: dict[str, Any] = {
        'id': preset_id,
        'source': 'user',
        'derived_from': base_preset_id or selected_preset_id(project_path),
        'defaults': _clone(config.get('defaults') or base.get('defaults') or {}),
    }
    for lang in ('en', 'zh', 'zh_tw', 'ja'):
        for field in ('label', 'desc'):
            key = f'{field}_{lang}'
            value = (labels or {}).get(key) or base.get(key)
            if value:
                preset[key] = value
    preset.setdefault('label_en', preset_id)
    if page_roles:
        preset['page_roles'] = page_roles
    preset['elements'] = elements
    return preset


def save_user_preset(preset: dict[str, Any]) -> Path:
    """Write one derived preset to ``overlay/animations/user/<id>.json``.

    Kept out of ``.gitignore`` on purpose: a preset is authored content. Whether
    to version-control it is the user's call, the same way a VSCode theme is.
    """
    preset_id = str(preset.get('id') or '')
    if not USER_PRESET_ID_RE.match(preset_id):
        raise ValueError(f'invalid preset id: {preset_id}')
    USER_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = USER_PRESETS_DIR / f'{preset_id}.json'
    payload = {key: value for key, value in preset.items() if key != 'path'}
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    os.replace(tmp, path)
    return path


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
