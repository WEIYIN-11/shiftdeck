# Upstream PR draft — add a `zh-TW` (Traditional Chinese) UI locale

> Target: `hugohe3/ppt-master`, based on `v4.5.0` (`ec824ae`).
> Status: draft, not yet submitted. Paste the body below into the PR description.

---

## Title

`feat(ui): add Traditional Chinese (zh-TW) locale to Confirm UI and SVG Editor`

## Body

### What this does

Adds Traditional Chinese (`zh-TW`) as a **fourth** UI language to the Confirm UI and the
SVG Editor, alongside the existing `en` / `ja` / `zh`.

This is **purely additive**. Not a single existing `en`, `ja`, or `zh` string is changed,
reordered, or removed — Simplified Chinese users see exactly what they see today. The
change is verifiable mechanically: parse `MESSAGES` before and after and the `en`/`ja`/`zh`
objects are byte-identical, and every non-`*_zh_tw` key in `catalogs.json` is unchanged.

### Why

Traditional Chinese and Simplified Chinese are not the same locale for a presentation
tool. Beyond the script, the vocabulary differs in exactly the places this UI lives:

| Concept | `zh` (current) | `zh-TW` (added) |
|---|---|---|
| slide | 幻灯片 | 投影片 |
| template | 模板 | 範本 |
| apply | 应用 | 套用 |
| undo | 撤销 | 復原 |
| default | 默认 | 預設 |
| font | 字体 | 字型 |
| save | 保存 | 儲存 |
| refresh | 刷新 | 重新整理 |

Machine-converting the script alone would still read as a foreign locale to users in
Taiwan, so the strings were converted with OpenCC `s2twp` and then reviewed line by line
against Microsoft Office zh-TW terminology.

### Changed files

| File | Change |
|---|---|
| `skills/ppt-master/scripts/confirm_ui/static/app.js` | new `"zh-TW"` `MESSAGES` block (176 keys, full parity with `zh`); `LANG_FALLBACK` + `LANG_FIELD`/`langField()`; `LANG_NAMES`; `zh_tw` keys in `IMAGE_COMPARISON_LABELS`; `zh-TW` accepted by the tag parser, `applyServerLanguage()`, and `chooseLang()` |
| `skills/ppt-master/scripts/confirm_ui/static/catalogs.json` | `*_zh_tw` twin for all 172 `*_zh` fields (`label_zh_tw` / `desc_zh_tw` / `group_zh_tw` / `use_zh_tw`); `_comment` documents the new suffix |
| `skills/ppt-master/scripts/confirm_ui/static/index.html` | one `<li data-lang="zh-TW">繁體中文</li>` in the language menu |
| `skills/ppt-master/scripts/svg_editor/static/app.js` | new `"zh-TW"` `MESSAGES` block (73 keys, full parity with `zh`); `LANG_NAMES`; `zh-TW` accepted by the tag parser and `setLang()` |
| `skills/ppt-master/scripts/svg_editor/static/index.html` | one `<li data-lang="zh-TW">繁體中文</li>` in the language menu |

`server.py` is untouched. `_build_catalogs()` copies unknown catalog fields verbatim, so
`/api/catalogs` serves the new fields with no server change.

### Design notes

**Field suffix vs. BCP-47 tag.** `localized(obj, base)` looks up `base + "_" + LANG`, and
`label_zh-TW` is not a usable JSON/JS field name. The tag stays `zh-TW` everywhere it is
user- or browser-facing (`localStorage`, `<html lang>`, `data-lang`, the server's `lang`
field); a small `langField()` maps it to the `zh_tw` field suffix for data lookups only.
`LANG_FALLBACK` values were already field suffixes, so the new entry reads
`"zh-TW": ["zh_tw", "zh", "en", "ja"]` and both existing consumers work unchanged.

**Fallback is safe for agent-authored data.** Recommendation files written by the agent do
not have to carry `*_zh_tw`. When a field is missing, a `zh-TW` user falls back to `zh`
before `en` — the same relative behavior the other locales already have. Existing
recommendation files keep working with no migration.

**Browser detection.** `zh-TW` / `zh-HK` / `zh-MO` / `zh-Hant` navigator tags now resolve to
`zh-TW`; every other `zh*` tag still resolves to `zh` exactly as before.

**Font labels are display-only.** `catalogs.json` font entries keep their `id`
(`Microsoft YaHei`, `SimHei`, `Yu Gothic`, …) untouched — that is what reaches the SVG
`font-family` and the PPTX export. Only `label_zh_tw` was translated, and
`fontChoiceLabel()` always renders `label · id`, so the identifier stays visible and font
matching never depends on the label text. Japanese faces use Taiwanese typographic names
in their `zh-TW` label (`游ゴシック` → 游黑體, `MS Mincho` → MS 明體) while `label_ja` and
`id` are unchanged. Product names are transliterated but not renamed (小红书 → 小紅書,
公众号 → 公眾號), and SVG / PPTX / DrawingML / matrix / tspan stay untranslated.

### How to test

1. Start either UI:
   ```bash
   python3 skills/ppt-master/scripts/confirm_ui/server.py <project_path> --daemon
   python3 skills/ppt-master/scripts/svg_editor/server.py <project_path> --live --daemon
   ```
2. Open the language dropdown in the top right — it now lists 繁體中文. Select it: labels,
   placeholders, tooltips, section headers, modal text, and the catalog-driven option
   cards switch to Traditional Chinese.
3. Switch back to 中文 / English / 日本語 and confirm nothing changed.
4. Reload — the choice persists via `localStorage["ppt_lang"] === "zh-TW"`, and
   `document.documentElement.lang` is `zh-TW`.
5. `GET /api/catalogs` returns the `*_zh_tw` fields; `GET /api/recommendations` with
   `"lang": "zh-TW"` in `template_options.json` opens the page already in Traditional
   Chinese.
6. Sanity checks:
   ```bash
   node --check skills/ppt-master/scripts/confirm_ui/static/app.js
   node --check skills/ppt-master/scripts/svg_editor/static/app.js
   python3 -c "import json;json.load(open('skills/ppt-master/scripts/confirm_ui/static/catalogs.json',encoding='utf-8'))"
   ```

### Verified before opening this PR

- `node --check` passes on both `app.js`; `catalogs.json` parses.
- `zh-TW` key sets equal the `zh` key sets exactly (176 and 73 keys, same order, no
  missing or extra keys), so no key can fall through to English.
- All 172 `*_zh` catalog fields have a `*_zh_tw` twin.
- A character-level scan (OpenCC `s2t`) finds no Simplified residue in any `zh-TW` string.
- `en` / `ja` / `zh` `MESSAGES` objects and all non-`*_zh_tw` catalog content are
  byte-identical to `v4.5.0`.
- The Confirm UI server boots against a real project and serves the new fields.

### Not in scope

No refactoring, no changes to `server.py`, no changes to the existing locales. Kept as
small as possible on purpose.
