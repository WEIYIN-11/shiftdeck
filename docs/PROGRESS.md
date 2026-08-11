# shiftdeck 進度

> 最後更新：2026-08-11 21:35
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
| 3 動畫選擇器 | 🔄 進行中（背景 agent） | — |
| 4 單頁重生成 | ⏸ 等待階段 3（同改 `svg_editor/app.js`） |

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

## 待你授權

**上游 PR 尚未送出**。草稿在 `docs/upstream-pr-draft.md`，推到公開 repo 需要你明確授權（agent 未代為 fork 或 push，這是對的）。

## 技術發現（已寫入 contract）

1. **多行文字必須用「全 `<tspan>`」形式，第一行 `dy="0"`**。混寫「直接文字 + 定位 tspan」會讓 checker 的 `_positioned_text_lines` 直接 return None——**靜默失去版面溢出檢查**。這是規範文字與驗證器行為的真實落差。
2. **未宣告字級在同一份 deck 出現超過 2 次是 error 而非 warning**。頁型用到的字級必須寫進 `spec_lock.md ## typography`。

## 已修正的坑

`engine.lock` 原鎖 `b6ed57c0`（main HEAD），但 `v4.5.0` tag 實際指向 `ec824aec`，兩版 `confirm_ui/app.js` 有實質差異會使行號失準。已改鎖正式 tag（commit `cec095d`）。

## 下一步

1. 階段 3 完成 → 驗收（重點：**未選動畫時不可造成回歸**、動畫節點要在 OOXML 層驗證、新 UI 字串要有四語言）
2. 派階段 4（`docs/handoff/stage4-single-page.md`）
3. 全部完成後：人工驗收清單 → 授權送 PR → 發布

派工指令格式：

```
讀 docs/PROGRESS.md 與 docs/handoff/stage4-single-page.md，執行階段 4
```
