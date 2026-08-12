# Upstream PR draft — add a `zh-TW` (Traditional Chinese) UI locale

> Target: `hugohe3/ppt-master`, based on `v4.5.0` (`ec824ae`).
> **Status: 已送出（2026-08-12）** — PR https://github.com/hugohe3/ppt-master/pull/259 ，
> 先開的 issue https://github.com/hugohe3/ppt-master/issues/258 。
> 本檔保留為當時送出的內容與判斷理由；後續往來以 GitHub 上為準。

---

## ⚠️ 送出前必讀：上游的貢獻政策與這個 PR 的衝突

`CONTRIBUTING.md` 有兩條直接命中這個 PR：

1. **「Translations & wording-only edits — please open an issue rather than a PR.」**
   理由寫得很明白：未經邀請的翻譯檔會產生沒有負責人的長期同步負擔。
   「Not a fit」清單裡也列了「Pure translations or wording-only edits that were not
   requested or discussed first」。這個 PR 有 421 行是翻譯字串。
2. **「Substantial features, new abstractions — please open an issue first to discuss
   fit and direction. PRs submitted without prior discussion may be closed without
   detailed review.」** 新增第四語言（含 `langField()` / `LANG_FALLBACK` 新機制）算這一類。

反面論點：`confirm_ui/server.py` 那一行是**貨真價實的 bug fix**（有 409 重現步驟），
而 bug fix 是他們明確歡迎的類別。但它只佔 1 行，不足以讓整個 PR 換一個分類。

**維護者是 solo，PR 模板三個勾選框有一個沒勾就直接關閉。**
建議路徑：先開 issue（附 fork 分支連結讓對方看 diff）問要不要收，受邀再開 PR。
若決定直接開 PR，就要接受「可能被 close without detailed review」的結果——
但即使被關，程式碼仍留在 `overlay/patches/01-zh-tw-locale.patch`，shiftdeck 完全不受影響。

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

Almost all of it is front-end. The one server-side line is a real bug the locale exposes:
`_localized_text_present()` does not know about `*_zh_tw`, so a Stage 2 recommendation
file written only in Traditional Chinese is rejected with a 409 even though the prose is
present. Details and a full before/after truth table are below.

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
| `skills/ppt-master/scripts/confirm_ui/server.py` | one line: `_localized_text_present()` also accepts a `*_zh_tw` field |

Everything else in `server.py` is untouched. `_build_catalogs()` copies unknown catalog
fields verbatim, so `/api/catalogs` serves the new `*_zh_tw` fields with no server change.

### The one server-side line, and why it is needed

`_localized_text_present()` is the Stage 2 gate for agent-authored prose. It accepts a
field when any of `field`, `field_zh`, `field_en`, `field_ja` is a non-empty string:

```python
for key in (field, f'{field}_zh', f'{field}_en', f'{field}_ja')
```

`*_zh_tw` is not in that tuple, so a Stage 2 recommendation file whose
`custom_candidates` / `design_directions` prose is written **only** in Traditional
Chinese is rejected — the strings are there, but the server cannot see them:

```
GET /api/recommendations
409  {"error":"custom_candidates.mode requires non-empty localized name"}
```

That is reachable today, not hypothetically: the agent writes those files in the deck's
main language, and once the UI offers `zh-TW` a Taiwanese user's deck is authored in
`zh-TW`. Adding `f'{field}_zh_tw'` to the tuple is the whole fix.

The change can only widen acceptance. Enumerating the input space:

| candidate | upstream v4.5.0 | with this change |
|---|---|---|
| `name` (bare) | True | True |
| `name_zh` only | True | True |
| `name_en` only | True | True |
| `name_ja` only | True | True |
| `name_zh` + `name_zh_tw` | True | True |
| all four suffixes | True | True |
| empty / blank / non-string | False | False |
| **`name_zh_tw` only** | **False** | **True** |

Exactly one input class changes verdict, and it is the one that is currently a false
rejection. No existing file can start failing.

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
6. Reproduce the server-side 409 and confirm the fix. On a project sitting at Stage 2
   (`result.json` = `stage1-confirmed`, valid `template_selection.json` /
   `template_handoff.json`), write a `recommendations.stage2.json` whose
   `custom_candidates` and `design_directions` prose uses only `*_zh_tw` fields
   (`name_zh_tw`, `behavior_zh_tw`), then:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5050/api/recommendations
   ```
   On `v4.5.0` this is `409 custom_candidates.mode requires non-empty localized name`;
   with this change it is `200` and the response carries the `*_zh_tw` prose.
7. Sanity checks:
   ```bash
   node --check skills/ppt-master/scripts/confirm_ui/static/app.js
   node --check skills/ppt-master/scripts/svg_editor/static/app.js
   python3 -c "import json;json.load(open('skills/ppt-master/scripts/confirm_ui/static/catalogs.json',encoding='utf-8'))"
   python3 -m py_compile skills/ppt-master/scripts/confirm_ui/server.py
   ```

### Verified before opening this PR

Run against a worktree of `v4.5.0` (`ec824ae`) with only this change applied:

- `node --check` passes on both `app.js`; `catalogs.json` parses; `server.py` compiles.
- `zh-TW` key sets equal the `zh` key sets exactly (176 and 73 keys, same order, no
  missing or extra keys), so no key can fall through to English.
- All 172 `*_zh` catalog fields have a `*_zh_tw` twin.
- A character-level scan (OpenCC `s2t`) finds no Simplified residue in any `zh-TW` string.
- `en` / `ja` / `zh` `MESSAGES` objects, the 20 inline image-comparison label rows, and all
  non-`*_zh_tw` catalog content (49,435 bytes compared) are byte-identical to `v4.5.0`.
  Each `index.html` gains exactly one line and loses none.
- **The 409 was reproduced over real HTTP**, on a project built with `project_manager.py
  init` and a Stage 2 recommendation file written only in Traditional Chinese:
  `v4.5.0` → `409 custom_candidates.mode requires non-empty localized name`;
  with the one-line change → `200`, serving the `*_zh_tw` prose. Same fixture, same
  server, only that line differs.
- `_localized_text_present()` was exercised across all 11 input classes in the table above;
  only `*_zh_tw`-only flips, and it flips `False → True`.

### Not in scope

No refactoring, no changes to the existing locales, and no other change to `server.py`
beyond the single tuple entry. Kept as small as possible on purpose.

### Confirmations

<!-- The PR template requires all three. Box 2 is the reason the full diff must be read
     by a human before this is submitted — do not tick it on the model's say-so. -->

- [x] I have read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [x] I personally reviewed the full diff and verified every claim in this description
      against this repository's actual code — including that the problem is real here and
      the capability isn't already provided by an existing path or already fixed on `main`
- [x] This PR is code-only — no `SKILL.md`, `references/*.md`, or `workflows/*.md` text is
      touched. The changed files are two `app.js`, two `index.html`, `catalogs.json`, and
      one line of `confirm_ui/server.py`.
