# 階段 1：繁體中文介面

> 冷啟動可執行。先讀 [`../decisions.md`](../decisions.md) 了解專案脈絡。
> **本階段同時是偵察**——讀完 707 個字串就摸熟了階段 3 要動刀的兩個檔案。

## 目標

在引擎的 UI 加入 `zh-TW` 語言選項（**新增第四語言，不是改掉簡中**），並把成果 PR 回上游。

## 前置條件

```bash
python scripts/setup.py        # 引擎就緒
python scripts/setup.py --check
```

## 已查證的事實

> 行號與字串數已對 **v4.5.0 (ec824aec)** 實測校正過，可直接引用。

引擎路徑一律相對於 `vendor/ppt-master/skills/ppt-master/scripts/`。

| 檔案 | 中文字串 | i18n 結構 |
|---|---|---|
| `confirm_ui/static/app.js` | 345 | `MESSAGES` 物件（L13）三區塊：`en`(L14)／`ja`(L192)／`zh`(L370)；`LANG` 解析 L550；`LANG_FALLBACK` L568（消費點 L598、L638）；另有內嵌多語對照表 |
| `confirm_ui/static/catalogs.json` | 223 | 欄位為 `label_zh` / `desc_zh` / `group_zh`（另有 `_en` / `_ja`） |
| `svg_editor/static/app.js` | 139 | `MESSAGES`：`en`(L10)／`ja`(L85)／`zh`(L160)；`LANG` 解析 L237；`LANG_NAMES` L276（消費點 L281） |

- 語言偏好存於 `localStorage["ppt_lang"]`
- Server 與 HTML **零硬編碼中文**，不需改動
- 現有 `zh` 為簡體（如「切换语言」「公众号头图」「微软雅黑」）

## 工作內容

1. **新增語言區塊**：兩個 `app.js` 的 `MESSAGES` 各加一個 `"zh-TW"` 區塊；更新 `LANG_FALLBACK`（建議 `"zh-TW": ["zh-TW", "zh", "en", "ja"]`）與 `LANG_NAMES`（`"繁體中文"`）。
2. **catalogs.json**：每個帶 `_zh` 的欄位補上對應的 `_zh_tw`。
3. **內嵌對照表**：`confirm_ui/app.js` L587 之後的多語 label 物件同樣補 `zh_tw` 鍵。
4. **翻譯方法**：OpenCC `s2twp` 模式自動轉換（含台灣用語：視頻→影片、軟件→軟體、屏幕→螢幕），**然後逐條人工校對**。特別注意：字型名稱（「微软雅黑」是 Windows 字型 ID，**不可翻譯**）、格式名稱（「小红书」是產品名，保留但轉繁）、技術術語。
5. **產出兩份東西**：
   - `overlay/patches/01-zh-tw-locale.patch`（`git diff` 於引擎目錄產生），並在 `engine.lock` 的 `patched_files` 登記三個檔案
   - 給上游 hugohe3/ppt-master 的 PR（純加法，不動現有 `zh`）

## 驗收標準

- [ ] 兩個 UI 的語言切換器出現「繁體中文」選項，切換後介面全繁中
- [ ] 掃描腳本在 `zh-TW` 區塊找不到簡體殘留（可用常見簡體字集比對）
- [ ] 字型下拉的字型名稱**未被誤翻**（`Microsoft YaHei` / 「微软雅黑」在字型識別上下文須保持可用）
- [ ] 切換回 `zh` / `en` / `ja` 功能完好無損
- [ ] `python scripts/setup.py --overlay` 能乾淨套用 patch
- [ ] PR 已送出，連結記錄於本文件底部

## 禁止事項

- **不要改掉現有 `zh` 區塊**——那會讓 PR 無法被接受，也會傷害簡中使用者
- 不要順手重構 `app.js` 的其他部分（PR 越單純越容易被接受）
- ~~不要碰 `server.py`~~ ——**2026-08-12 E6 已推翻這條**，見下方「E6」。原本的理由（無硬編碼中文）
  是對的，但漏看了 `_localized_text_present()` 的 suffix 白名單，那是繁中化真正的伺服器端缺口。

## 完成後

更新 `engine.lock` 的 `patched_files`，並在此記錄 PR 連結：`（待送出）`

- 譯文與 patch 已完成：`overlay/patches/01-zh-tw-locale.patch`，`engine.lock` 已登記 5 個檔案。
- PR 描述草稿：[`../upstream-pr-draft.md`](../upstream-pr-draft.md)（英文，可直接貼進 PR）。
- 回歸檢查：`python scripts/check_zhtw.py`（掃簡體殘留 + key 對齊 + 切換器可達性）。
- **多改了兩個檔案**：`confirm_ui/static/index.html` 與 `svg_editor/static/index.html`。語言選單的
  `<li>` 是寫死在 HTML 裡的，只改 `LANG_NAMES` 使用者仍然選不到繁體中文；各加一行。

## E6：伺服器端的繁中缺口（2026-08-12 補上）

`confirm_ui/server.py` 的 `_localized_text_present()` 用一組寫死的 suffix 判斷「這個候選項
有沒有寫文案」，白名單只有 `field` / `_zh` / `_en` / `_ja`。**`_zh_tw` 不在裡面**，所以
stage2 推薦檔的 `custom_candidates` 與 `design_directions` 只寫繁中時，字明明在檔案裡，
伺服器卻看不到，`GET /api/recommendations` 回 409。

改動就一行——tuple 補一個 `f'{field}_zh_tw'`。

**驗證方式（真實 HTTP，非推論）**：用 `project_manager.py init` 建真專案，補齊
`template_options` → `template_selection` → `result(stage1-confirmed)` → `template_handoff`
→ `recommendations.stage2.json`（文案全部只寫 `name_zh_tw` / `behavior_zh_tw`），
同一份 fixture、同一支伺服器，只差那一行：

| 版本 | `GET /api/recommendations` |
|---|---|
| 上游 v4.5.0 | `409 custom_candidates.mode requires non-empty localized name` |
| 補完 `_zh_tw` | `200`，回應裡帶著 `*_zh_tw` 文案 |

另外把 `_localized_text_present()` 的 11 種輸入形態逐一比對新舊實作：**只有「只寫 `_zh_tw`」
這一類從 `False` 變 `True`**，其餘（裸欄位／只寫 zh／只寫 en／只寫 ja／空字串／空白字串／
非字串／四種都寫……）結果完全相同。純加法，不可能讓既有檔案開始失敗。

**為什麼併進 01 而不另開 05 patch**：E6 是同一個 PR 的伺服器端另一半，放在 01 的話
「上游合併 → 整個 patch 刪掉」這個乾淨性質才成立；獨立成 05 的話它的基準會是
01→03→04 之後的樹，抽不出乾淨的上游 diff，還多一筆刪除債。已驗證 01（含 E6）→03→04
依序套用後的 tree SHA `78bc80bc` 與工作區完全相同，E6 插入的那行沒有讓 03/04 失準。

`engine.lock` 的 `patched_files` 早在階段 3 就已登記 `confirm_ui/server.py`，不必新增項目。

## PR（2026-08-12 已送出）

| 項目 | 連結 |
|---|---|
| **PR** | https://github.com/hugohe3/ppt-master/pull/259 |
| **Issue**（先開，PR 內文第一行連過去） | https://github.com/hugohe3/ppt-master/issues/258 |
| fork | https://github.com/WEIYIN-11/ppt-master |
| branch | `feat/zh-tw-locale`，commit `d2fa67f`，基準 `ec824ae`（v4.5.0） |

**PR 實際內容**（GitHub 上核對過）：6 個檔案、482 增 35 刪，與
`overlay/patches/01-zh-tw-locale.patch` 完全一致。**階段 2／3／4 的東西一個都沒混進去**
（`finalize_svg.py`、`svg_to_pptx.py`、`svg_editor/server.py`、`overlay/` 全部不在清單裡）。

**為什麼先開 issue**：上游 `CONTRIBUTING.md` 明訂「Translations & wording-only edits —
please open an issue rather than a PR」，且「Not a fit」清單直接列了未經討論的純翻譯；
新增語言又落在「Substantial features… may be closed without detailed review」。
所以先開 issue 說明來意並附 compare 連結，PR 內文第一行連回 issue，並主動寫明
「若只想收那一行 server.py 的 bug fix，說一聲我就把其餘拿掉」。

PR 模板的三個勾選框已全部勾選——第二個框（本人已審過完整 diff）是使用者在送出前
逐項看過 diff 後才勾的，不是 agent 代勾。

**若上游合併**：`overlay/patches/01-zh-tw-locale.patch` 整份刪除，`engine.lock` 的
`patched_files` 移除五個 static 檔（`confirm_ui/server.py` 要留著，階段 3 還在用），
`scripts/check_zhtw.py` 可保留當作升級後的回歸檢查。
