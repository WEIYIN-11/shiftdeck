# shiftdeck 進度

> 最後更新：2026-08-12 09:05
> 本檔是 session 之間的交接點。開新 session 時先讀這份，再讀對應的 `handoff/`。

## 環境

| 項目 | 狀態 |
|---|---|
| 引擎 | ✅ `v4.5.0` / `ec824aec`，14,056 檔案 |
| 依賴 | ✅ 已安裝 |
| 檢查 | `python scripts/setup.py --check` · `python scripts/check_zhtw.py` |

## 階段狀態

| 階段 | 狀態 | commit |
|---|---|---|
| 1 繁中化 | ✅ 完成並驗收 | `8cedaca` |
| 2 頁型庫 | ✅ 完成並驗收 | `07c15f6` |
| 3 動畫選擇器 | ✅ 完成並提交 | `d4450d8` |
| 4 單頁重生成 | ⏸ 可開工（階段 3 已釋出 `svg_editor/app.js`） | — |

**依賴**：1 → 3 → 4 為純序列（都動 `svg_editor/static/app.js`）。階段 2 已與 1 並行完成。

## 驗收紀錄

### 階段 1（繁中化）

獨立驗證，非採信 agent 自述：

- **Node 實際執行比對 MESSAGES**：兩個 app.js 的 `en`/`ja`/`zh` byte-identical；新增 `zh-TW` key 數與 `zh` 完全對齊（176/176、73/73）
- `catalogs.json` 去除 `_zh_tw` 與 `_comment` 後與原版全等，新增 172 個欄位
- 20 個多語對照表的 `zh` 值變動 0 項
- patch 與工作區 diff 完全一致；`check_zhtw.py` 18 項全過
- 實改 **5 個檔案**（非交接文件預估的 3 個）——語言選單的 `<li>` 硬編碼在兩個 `index.html`，各加一行

**驗收過程中我自己犯的兩次誤報**（教訓：檢測工具本身也要驗證）：
1. 用正則抓區塊，因假設 `zh/en/ja` 固定順序而失準 → 改用 Node 實際執行才可靠
2. 自製簡體字集混入繁簡同形字（容、片），誤報 27 條 → 實際譯文「投影片」「圖片產製」全部正確

**OpenCC 的四處過度轉換，現版才是對的**：社群≠社羣、平台≠平臺、游黑體≠遊黑體（Yu Gothic 台灣譯名）。agent 的人工校對優於機械轉換。

### 階段 2（頁型庫）

- 獨立重跑 `svg_quality_checker --stage final`：四個骨架 **0 errors / 0 warnings**
- contract 含**佔位色換色表**（8 個中性色 → `colors.*` 角色）、字級角色對應、字數上限
- KPI 測過 3／6 指標，流程圖測過 3／4／7 節點

### 階段 3（動畫選擇器）

實跑驗證，全部通過：

- **三套組**：專業沉穩（fade 0.35s＋全淡入，chart 用 wipe）／輕快活潑（push up 0.5s＋飛入·縮放·逐項，takeaway 追加 grow_shrink）／極簡無干擾（fade 0.25s，頁內 0 列）
- **OOXML 層驗證**（解壓 .pptx 比對 `p:cTn presetID/presetClass/presetSubtype` 與 sidecar）：professional 23 列、lively 26 列、minimal 0 列、none 0 列，順序與效果逐列吻合
- **零回歸**：未選動畫時不寫 `animations.json`，匯出仍是 `fade@400ms` ＋ 0 動畫列，與改動前 baseline 完全一致
- **confirm_ui HTTP 端到端**：stage1 → handoff → stage2 → final，選擇結果同時寫入 `result.json.deck_animation` 與 `<專案>/animations.json`（無 BOM）；未知套組回 400 且不落地任何檔案
- **svg_editor API**：未知效果／不存在的 group／`order=0` 都被引擎驗證器擋下並回 400
- **單元素即時預覽**：瀏覽器實測 translate／clip-path／scale 三族都真的在動，播完自動還原無殘留 inline style
- `check_zhtw.py` 18 項全過（新增 28 個 UI 字串 × 4 語言）


### 使用者驗收回饋與處置（2026-08-12）

| 回饋 | 處置 |
|---|---|
| 第一頁文字跑出格（LibreOffice 開啟） | ✅ **已修**。根因：儲存格「CJK＋拉丁」混排字寬被低估 7-10%，LibreOffice 度量更寬且強制重斷行。修法：佔位文字改純 CJK 單行、contract 上限下修 15%。LibreOffice 重渲染確認乾淨 |
| 使用者環境**只有 LibreOffice、沒有 PowerPoint** | 動畫觀感驗收改以 LibreOffice 為準；D1/D2 的 PowerPoint 項目降級為「有機會再驗」 |
| 動畫套組「前兩種區別不大、第三種等於沒有」 | ⏳ **待使用者決定**：已提「五個場景型套組」重設計方向（沉穩／逐項聚焦／活潑／數據揭示／戲劇登場，移除 minimal），等使用者拍板後重做 presets.json |
| B（繁中）、C（頁型設計取捨） | ✅ 使用者確認 OK |

### 新標準閘門：LibreOffice 視覺驗證

`python scripts/visual_check.py <匯出檔> [-o 目錄]` —— .pptx → LibreOffice 轉 PDF → PyMuPDF 逐頁 PNG。
**每個匯出物都要過兩道**：`svg_quality_checker`（幾何估算）＋ `visual_check`（真實字型渲染）。
這是從使用者實際回饋反推出的功能：checker 對跑版頁報 0 errors，人眼一看就發現撐框。
原 v2 的「vision 視覺自檢」提前實現了一半（渲染管線就緒，AI 自動看圖迴路留給階段 4 之後）。

## 待人工驗收（agent 看不到 UI，必須人眼確認）

### 階段 1
1. 語言選單真的看得到「繁體中文」，切換後整頁生效，切回 zh/en/ja 無損
2. **版面是否爆版**——「繁體中文」比「中文」多兩字，語言按鈕與下拉寬度
3. 字型下拉顯示 `微軟雅黑 · Microsoft YaHei`，選取後送出的仍是英文 id
4. svg_editor 的動態區塊（選取面板、標註列表）切換語言後即時重繪
5. 18 種視覺風格卡片的繁中描述是否斷行怪異
6. 清掉 `localStorage["ppt_lang"]` 後，瀏覽器語系 zh-TW 是否自動選繁中

### 階段 2
7. **在 PowerPoint 開啟測試 .pptx**，確認方框與箭頭是可選取的原生圖形：
   `C:\Users\try19\AppData\Local\Temp\claude\C--Users-try19-Desktop-resourse\22d00681-ebd0-4093-a48b-d3e0b3d5b07f\scratchpad\vendorcheck\exports\vendorcheck_20260811_183540.pptx`
8. 流程圖 5／6 節點佈局未實跑（3／4／7 已驗證），首次使用時看一眼
9. 頁型縮圖尚未產出 PNG；若階段 4 選擇器需要點陣圖，要先決定 rasteriser

### 階段 3
10. **在 PowerPoint 開啟四份測試 .pptx**，確認動畫真的照設定播放（agent 只能驗到 XML 節點存在且結構正確，驗不到 PowerPoint 的實際觀感）。資料夾：
    `C:\Users\try19\AppData\Local\Temp\claude\C--Users-try19-Desktop-resourse\22d00681-ebd0-4093-a48b-d3e0b3d5b07f\scratchpad\stage3-exports\`
    內含 `stage3_professional.pptx`／`stage3_lively.pptx`／`stage3_minimal.pptx`／`stage3_none.pptx` 與各自的 `*.animations.json`。**`none` 那份是回歸對照組**，動畫窗格應該完全是空的。
11. **瀏覽器預覽與 PowerPoint 的方向感是否一致**——`entrance_fly` 的 `direction` 指的是「從哪個邊進來」，`entrance_wipe` 指的是「擦除掃過的方向」，兩者語意不同但共用同一組上／右／下／左標籤。預覽是唯一的消歧手段，值得人眼比對一次
12. 動畫面板在右側欄的**版面是否過擠**（效果列有 2 個下拉＋2 個按鈕，繁中標籤比英文長）
13. `entrance_split` 的 `_in` / `_out` 在瀏覽器預覽裡是同一個動作（單一 `clip-path` 無法表達兩段式揭示）；匯出的 PPTX 是正確的，只有預覽是近似

## 待你授權

**上游 PR 尚未送出**。草稿在 `docs/upstream-pr-draft.md`，推到公開 repo 需要你明確授權（agent 未代為 fork 或 push，這是對的）。

## 技術發現（已寫入 contract）

1. **多行文字必須用「全 `<tspan>`」形式，第一行 `dy="0"`**。混寫「直接文字 + 定位 tspan」會讓 checker 的 `_positioned_text_lines` 直接 return None——**靜默失去版面溢出檢查**。這是規範文字與驗證器行為的真實落差。
2. **未宣告字級在同一份 deck 出現超過 2 次是 error 而非 warning**。頁型用到的字級必須寫進 `spec_lock.md ## typography`。
3. **`animations.json` 頂層只認 `version` / `defaults` / `slides`**，多一個 key 就驗證失敗——所以套組 id 不能存在 sidecar 裡，改存 `confirm_ui/result.json` 的 `deck_animation.preset`。
4. **`defaults.animation.effect: "none"` 不會壓掉明列的 group 效果**（實測 26 列都有寫出來）。這正是精準控制的做法：只有列出來的 group 會動。
5. **`direction` 的語意隨效果族而變**：`entrance_fly` 的 `up` 是「從上方進來」（往下移動），`entrance_wipe` 的 `up` 是「往上擦除」。registry 的 `row_xml` 是唯一可信來源，不要照字面猜。
6. **上游 `_localized_text_present()` 只認 `_zh` / `_en` / `_ja`，不認 `_zh_tw`**（`confirm_ui/server.py`）。stage2 推薦檔的 `custom_candidates` 與 `design_directions` 只寫繁中會被 409 擋下。階段 1 沒動它是對的，但這是繁中化尚未覆蓋到的一角。

## 已修正的坑

`engine.lock` 原鎖 `b6ed57c0`（main HEAD），但 `v4.5.0` tag 實際指向 `ec824aec`，兩版 `confirm_ui/app.js` 有實質差異會使行號失準。已改鎖正式 tag（commit `cec095d`）。

## 階段 3 的檔案地圖

| 檔案 | 角色 |
|---|---|
| `overlay/animations/presets.json` | 三套組配置＋元素分類規則＋每類 8 個常用效果的四語標籤（**唯一資料來源**） |
| `overlay/animations/shiftdeck_animations.py` | 共用函式庫：讀套組、展開成 sidecar、用引擎自己的驗證器把關、寫檔 |
| `overlay/animations/apply_preset.py` | CLI：`--preset <id>` 或 `--from-result`，把套組展開成完整的每頁每元素設定 |
| `overlay/patches/03-animation-selector.patch` | 引擎端接線（1,505 行，基準＝01 patch 套用後的樹） |

**vendor 端只有接線**：兩個 `server.py` 各加一段「往上找 `overlay/animations/`」的 bootstrap 與新 API，找不到就整組功能自動關閉、行為退回上游（已實測：把 overlay 改名後 `/api/animations` 回 `available:false`、`/api/animation-presets` 回空清單，兩個伺服器都正常啟動）。

## 下一步

1. 階段 3 驗收（人工項目見上方 10–13）→ 提交
2. 派階段 4（`docs/handoff/stage4-single-page.md`）
3. 全部完成後：人工驗收清單 → 授權送 PR → 發布

派工指令格式：

```
讀 docs/PROGRESS.md 與 docs/handoff/stage4-single-page.md，執行階段 4
```
