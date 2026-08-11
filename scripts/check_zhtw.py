#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression check for the zh-TW locale added to the vendored ppt-master UI.

Verifies that every zh string has a zh-TW counterpart, that no Simplified
characters leaked into the zh-TW data, and that the language switcher can
actually reach the new locale.

Usage:
    python scripts/check_zhtw.py            # exit 0 = pass, 1 = fail
    python scripts/check_zhtw.py --verbose  # also list every offending string

Dependencies:
    Standard library only. Uses OpenCC for a wider Simplified character set
    when ``opencc`` happens to be installed, otherwise falls back to the
    embedded set below (derived from the engine's own Simplified strings).
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "vendor" / "ppt-master" / "skills" / "ppt-master" / "scripts"
CONFIRM_JS = ENGINE / "confirm_ui" / "static" / "app.js"
CONFIRM_HTML = ENGINE / "confirm_ui" / "static" / "index.html"
CATALOGS = ENGINE / "confirm_ui" / "static" / "catalogs.json"
EDITOR_JS = ENGINE / "svg_editor" / "static" / "app.js"
EDITOR_HTML = ENGINE / "svg_editor" / "static" / "index.html"

# Simplified-only characters occurring in the engine's own zh strings.
# Fallback used when OpenCC is unavailable.
SIMPLIFIED_CHARS = set(
    "与业丝丢严个为么义书于产亲仅从仪众优会传体余侧关内册写决准几击则删别务动匀区华协单占参双"
    "发变叙叠台号后启员咨围国图圆场坏块声处备复头奥学实审对导将尽层属岩师带并库应开弃张强当录"
    "径态悬战户执报担拟择损换据摄数断无时显暂术朴机杂权条来极构标栏样档横欧残气汇沟没浅涂润渐"
    "温游满灯点状独环现画盖盘础确离种积称穷竖笔签简类红约级纪纸纹线组细织终经结绘络统继绪续综"
    "缀编缩网群脱艺节范荐蓝补衬装见规视览觉触计认训议记讲论设证评识词试话询该语误说请读谁调谨"
    "责败质贴资转软轻载较辑输边达过运还这进连迹适选递采释里钟销锁锐错键闭问间闻阅阶际险随静页"
    "项须顾预频颗题颜风饰鸦齐"
)

# Characters OpenCC rewrites to an old variant (臺, 羣, 巖, 遊) even though the
# plain form is the Taiwan standard: 平台, 群組, 板岩, 游明體.
ALLOWED = set("台游群岩")

CJK_RE = re.compile(r"[㐀-䶿一-鿿]")


def _simplified_detector():
    """Return a callable reporting the Simplified characters inside a string."""
    try:
        from opencc import OpenCC
    except ImportError:
        def detect(text):
            return sorted({c for c in text if c in SIMPLIFIED_CHARS and c not in ALLOWED})
        return detect, "embedded set"

    converter = OpenCC("s2t")
    cache = {}

    def detect(text):
        found = set()
        for char in CJK_RE.findall(text):
            if char in ALLOWED:
                continue
            if char not in cache:
                cache[char] = converter.convert(char) != char
            if cache[char]:
                found.add(char)
        return sorted(found)

    return detect, "OpenCC s2t"


DETECT, DETECT_SOURCE = _simplified_detector()


class Report:
    """Collect check results and render a single pass/fail summary."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.failures = 0

    def check(self, name, ok, details=()):
        status = "PASS" if ok else "FAIL"
        print("[%s] %s" % (status, name))
        if not ok:
            self.failures += 1
        if details and (self.verbose or not ok):
            for line in list(details)[: (None if self.verbose else 20)]:
                print("       %s" % line)


def read(path):
    return path.read_text(encoding="utf-8")


def messages_block(source, lang_key):
    """Return {key: value} for one MESSAGES language block of an engine app.js."""
    lines = source.splitlines()
    header = '        %s: {' % lang_key
    try:
        start = lines.index(header)
    except ValueError:
        return None
    block = {}
    pair = re.compile(r'^\s{12}([A-Za-z_][A-Za-z0-9_]*): "(.*)",?$')
    for line in lines[start + 1:]:
        if line.startswith("        }"):
            break
        match = pair.match(line)
        if match:
            block[match.group(1)] = match.group(2)
    return block


def walk_json(node, path="$"):
    """Yield (path, key, value, container) for every dict entry."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value, node
            yield from walk_json(value, "%s.%s" % (path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_json(value, "%s[%d]" % (path, index))


def check_messages(report, path, label):
    source = read(path)
    zh = messages_block(source, "zh")
    tw = messages_block(source, '"zh-TW"')
    report.check("%s: MESSAGES has a zh-TW block" % label, bool(tw))
    if not tw or not zh:
        return
    missing = [k for k in zh if k not in tw]
    extra = [k for k in tw if k not in zh]
    report.check(
        "%s: zh-TW covers every zh key (%d keys)" % (label, len(zh)),
        not missing and not extra,
        ["missing: %s" % k for k in missing] + ["unexpected: %s" % k for k in extra],
    )
    offenders = []
    for key, value in tw.items():
        found = DETECT(value)
        if found:
            offenders.append("%s -> %s | %s" % (key, "".join(found), value))
    report.check("%s: zh-TW block has no Simplified residue" % label, not offenders, offenders)


def check_inline_tables(report, path, label):
    source = read(path)
    values = re.findall(r'zh_tw: "([^"]*)"', source)
    report.check("%s: inline zh_tw labels present" % label, bool(values))
    offenders = []
    for value in values:
        found = DETECT(value)
        if found:
            offenders.append("%s | %s" % ("".join(found), value))
    report.check("%s: inline zh_tw labels have no Simplified residue" % label,
                 not offenders, offenders)


def check_catalogs(report):
    try:
        data = json.loads(read(CATALOGS))
    except json.JSONDecodeError as exc:
        report.check("catalogs.json parses as JSON", False, [str(exc)])
        return
    report.check("catalogs.json parses as JSON", True)
    missing = []
    offenders = []
    total = 0
    for path, key, value, container in walk_json(data):
        if not key.endswith("_zh") or key == "_zh":
            continue
        total += 1
        twin = key + "_tw"
        if twin not in container:
            missing.append("%s.%s" % (path, key))
            continue
        found = DETECT(str(container[twin]))
        if found:
            offenders.append("%s.%s -> %s | %s" % (path, twin, "".join(found), container[twin]))
    report.check("catalogs.json: every *_zh field has *_zh_tw (%d fields)" % total,
                 not missing, missing)
    report.check("catalogs.json: *_zh_tw values have no Simplified residue",
                 not offenders, offenders)


def check_switcher(report):
    for path, label in ((CONFIRM_JS, "confirm_ui"), (EDITOR_JS, "svg_editor")):
        source = read(path)
        report.check('%s: LANG_NAMES lists zh-TW' % label,
                     '"zh-TW": "繁體中文"' in source)
        report.check('%s: localStorage accepts the zh-TW tag' % label,
                     'stored === "zh-TW"' in source)
    confirm = read(CONFIRM_JS)
    report.check("confirm_ui: LANG_FALLBACK maps zh-TW to the zh_tw field suffix",
                 '"zh-TW": ["zh_tw", "zh", "en", "ja"]' in confirm)
    for path, label in ((CONFIRM_HTML, "confirm_ui"), (EDITOR_HTML, "svg_editor")):
        report.check('%s: language menu offers 繁體中文' % label,
                     'data-lang="zh-TW"' in read(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="list every offending string instead of the first 20")
    args = parser.parse_args()

    if not ENGINE.exists():
        print("engine not installed at %s — run scripts/setup.py first" % ENGINE)
        return 2

    print("Simplified detector: %s\n" % DETECT_SOURCE)
    report = Report(verbose=args.verbose)
    check_catalogs(report)
    check_messages(report, CONFIRM_JS, "confirm_ui")
    check_messages(report, EDITOR_JS, "svg_editor")
    check_inline_tables(report, CONFIRM_JS, "confirm_ui")
    check_switcher(report)

    print("\n%d check(s) failed" % report.failures if report.failures else "\nAll checks passed")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
