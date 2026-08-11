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
- 不要碰 `server.py`（無硬編碼中文，改了只會擴大 diff）

## 完成後

更新 `engine.lock` 的 `patched_files`，並在此記錄 PR 連結：`（待填）`
