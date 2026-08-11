# shiftdeck 進度

> 最後更新：2026-08-11 18:45
> 本檔是 session 之間的交接點。開新 session 時先讀這份，再讀對應的 `handoff/`。

## 環境

| 項目 | 狀態 |
|---|---|
| 引擎 | ✅ 已安裝 `v4.5.0` / `ec824aec`，14,056 檔案 |
| 依賴 | ✅ python-pptx / PyMuPDF / Pillow / flask / edge-tts 均可匯入 |
| 檢查指令 | `python scripts/setup.py --check` |

## 階段狀態

| 階段 | 狀態 | 說明 |
|---|---|---|
| 1 繁中化 | 🔄 進行中 | 背景 agent 執行中，已改 5 個檔案（+481/−34 行） |
| 2 頁型庫 | ✅ 完成並驗收 | commit `07c15f6` |
| 3 動畫選擇器 | ⏸ 等待 | 前置：階段 1（同改兩個 app.js） |
| 4 單頁重生成 | ⏸ 等待 | 前置：階段 2（已完成）＋ 階段 3（同改 svg_editor/app.js） |

**依賴關係**：階段 1 → 階段 3 → 階段 4 為純序列（都動 `svg_editor/static/app.js`），不可並行。階段 2 已與階段 1 並行完成。

## 階段 2 驗收紀錄

獨立重跑（非採信 agent 自述）：
- `svg_quality_checker --stage final` 四個骨架 **0 errors / 0 warnings**
- 產出 8 個檔案（4 × `skeleton.svg` + `contract.md`）
- `vendor/` 未被階段 2 污染
- contract 含**佔位色換色表**（8 個中性色 → `colors.*` 角色）、字級角色對應、字數上限

### 待人工確認（agent 無法自驗）

1. **PowerPoint 開啟驗證**：四個骨架匯出的 .pptx 在
   `C:\Users\try19\AppData\Local\Temp\claude\C--Users-try19-Desktop-resourse\22d00681-ebd0-4093-a48b-d3e0b3d5b07f\scratchpad\vendorcheck\exports\vendorcheck_20260811_183540.pptx`
   需確認：開啟正常、文字可編輯、方框與箭頭是可選取的原生圖形。
2. **流程圖 5 與 6 節點佈局未實跑**（3／4／7 已驗證）。兩者與 7 節點共用四欄格線、幾何為子集，風險低，但首次實際使用時值得看一眼——會多出一個空的右上格。
3. **頁型縮圖尚未產出 PNG**。目前 `skeleton.svg` 本身即 1280×720 可渲染。若階段 4 的選擇器需要點陣縮圖，要先決定 rasteriser（引擎內無現成工具）。

## 技術發現（已寫入 contract，值得沉澱為專案指引）

1. **多行文字必須用「全 `<tspan>`」形式，第一行 `dy="0"`**。規範也允許「直接文字 + 定位 tspan」的混寫，但 checker 的 `_positioned_text_lines` 遇到 `<text>` 帶直接文字會直接 return None——結果是吐出 `Cannot verify root viewBox bounds` warning，**並且靜默失去版面溢出檢查**。這是規範文字與驗證器行為之間的真實落差。
2. **未宣告的字級在同一份 deck 出現超過 2 次是 error 而非 warning**。頁型用到的字級必須寫進 `spec_lock.md ## typography`。

## 已修正的坑

- `engine.lock` 原本鎖 `b6ed57c0`（main HEAD），但 `v4.5.0` tag 實際指向 `ec824aec`。兩版的 `confirm_ui/static/app.js` 有實質差異，會使交接文件行號失準。已改鎖正式 tag 並重新校正行號／字串數（707，非 717）。commit `cec095d`

## 下一步

1. 階段 1 完成 → 驗收（**特別檢查那 34 行刪除**：交接文件明令不得改動現有 `zh` 區塊）
2. 驗收通過 → 派階段 3
3. 階段 3 完成 → 派階段 4

開新 session 派工的指令格式：

```
讀 docs/PROGRESS.md 與 docs/handoff/stage3-animations.md，執行階段 3
```
