# 階段 4：單頁重生成 ＋ 動畫客製化

> 冷啟動可執行。先讀 [`../PROGRESS.md`](../PROGRESS.md)，再讀本文。
> ⚠️ **本階段是唯一必須 patch 引擎內部流程的工作**，不確定性最高。前三階段已是可用產品，這裡卡住不會拖垮專案。

## 優先順序（重要——時間或複雜度失控時照此取捨）

| 優先 | 項目 | 說明 |
|---|---|---|
| **P0 核心** | 單頁重生成 | 沒有它，v1 的產品承諾「單頁重做不用等全份」不成立 |
| **P0 核心** | 換頁型（接階段 2 的頁型庫） | 「頁型用挑的」的最後一哩，依賴單頁重生成 |
| P1 | 套組自動套用（原 E5） | 修掉一個確定會咬人的坑，見下 |
| P2 | ① 套組衍生與儲存 | 使用者親自指定要做 |
| P2 | ② 同類元素輪替 | 使用者親自指定要做 |

**P0 未完成前不要碰 P2。** 若 P0 完成但 P1/P2 只做得完一部分，回報時明確說明哪些沒做，不要硬塞半成品。

---

## P0-a 單頁重生成

### 現況

引擎流程是全量的：修改 → Executor 重畫 → **所有頁**重跑品質檢查 → `finalize_svg.py` 全量 → `svg_to_pptx.py` 全量重匯出。改一頁的代價等於整份。

相關路徑（`vendor/ppt-master/skills/ppt-master/`）：

| 檔案 | 角色 |
|---|---|
| `scripts/svg_quality_checker.py` | 已支援 `--stage first-page`——**已有單頁概念，是最重要的線索** |
| `scripts/finalize_svg.py` | 產生自包含預覽 |
| `scripts/svg_to_pptx.py` | 匯出 PPTX |
| `scripts/svg_editor/server.py` | 預覽編輯器後端（**已被階段 3 patch 過**，1,389 行 + 階段 3 新增） |
| `workflows/generate-pptx.md` | Step 6/7 流程規範 |
| `workflows/stages/live-preview.md` | 註解迴路既有規範 |

### 設計要點

**借用 open-slide 的選取狀態設計**（只借設計，不移植程式碼——那是 React/Vite 生態，與此處 Python／原生 JS 不相容）：

> dev server 把「使用者現在選取了什麼」寫進狀態檔，AI 讀它就知道「這個」「這一頁」指誰。

1. **選取狀態通道**：預覽編輯器把當前選取（頁碼、元素 id）寫進 `<專案>/live_preview/current.json`
2. **單頁重生成入口**：編輯器提供「換頁型／重畫本頁」動作，寫出重生成請求
3. **AI 端流程**：只重寫該頁 SVG → 只對該頁跑品質檢查 → 增量 finalize → 重新匯出
4. **匯出增量化**：最難的一步。先確認 `svg_to_pptx.py` 能否單頁替換；若不行，退而求其次——只重跑該頁 SVG 產出（省下最貴的 AI 重畫成本），匯出仍全量

## P0-b 換頁型

頁型庫在 `overlay/pagetypes/`（4 個，各有 `skeleton.svg` + `contract.md`）。

- 選擇器**直接用 `skeleton.svg` 當縮圖**（已決定：不轉 PNG，瀏覽器原生支援 SVG、零依賴、可無損縮放）
- 選定頁型後，AI 依該頁型的 `contract.md` 規則，用當前頁的內容重畫該頁
- **務必遵守 contract 裡的「跨軟體字型度量餘裕」規則**（2026-08-12 因 LibreOffice 跑版新增）

---

## P1 套組自動套用

**問題**：目前使用者在確認頁選了動畫套組後，還要**另外手動跑** `apply_preset.py --from-result` 才會展開成 `animations.json`。忘記跑 → 拿到沒動畫的成品，卻不知道為什麼。

**成因**：`animations.json` 頂層只認 `version`/`defaults`/`slides`，套組 id 塞不進去，只能暫存在 `confirm_ui/result.json` 的 `deck_animation.preset`。

**要做**：在 Generate Step 7 匯出前自動偵測並展開。找一個乾淨的接入點（例如 `svg_to_pptx.py` 啟動時檢查 `result.json` 有 `deck_animation.preset` 但 `animations.json` 不存在／過期，就自動展開）。**必須保持零回歸**：沒有 `deck_animation` 的專案行為完全不變。

---

## P2-① 套組衍生與儲存

**目標**：把「五個死的預設」變成「五個起點」。

- 使用者選一個套組 → 在編輯器裡改幾處 → **存成自己的套組**
- 儲存位置：`overlay/animations/user/<id>.json`（此目錄要加進 `.gitignore`？**不要**——使用者可能想版控自己的套組。改為在 README 說明可自行決定）
- 自訂套組要能出現在確認頁的套組清單裡，與內建的並列
- 格式沿用 `presets.json` 的 preset schema（`id`/`label_*`/`desc_*`/`defaults`/`page_roles`/`elements`）
- **設計意圖**：這是開源專案的正確形狀——像 VSCode 主題，社群可以分享「醫療簡報用」「工程評審用」的套組

## P2-② 同類元素輪替

**問題**：目前同一頁的 4 張卡片全部套同一個效果，只差 stagger 延遲，看起來機械。

**要做**：讓同類元素可以輪替效果或漸變參數。設計自由，但建議：

- 在 preset 的 element 定義裡支援 `rotate: [effectA, effectB]` 或 `progressive: {duration: [0.4, 0.3]}` 之類的表達
- **必須是選用的**——現有三套組不改行為（零回歸），新語法只在明確使用時生效
- 目標是消除「一眼看出是套用的」機械感，不是製造混亂

---

## 驗收標準（每項都要實跑）

### P0
- [ ] 預覽編輯器可對任一頁觸發「換頁型」，選單顯示 4 個頁型的 SVG 縮圖
- [ ] 只有該頁的 SVG 被重寫（其他頁檔案 mtime 不變）
- [ ] 只有該頁跑品質檢查
- [ ] **端到端耗時 < 全量重跑的 1/3**（實測數字填在本文底部）
- [ ] 重生成後的 .pptx，未改動頁面的內容與樣式完全一致
- [ ] `current.json` 每次導航／選取都更新，AI 讀取後能正確解析「這一頁」

### P1
- [ ] 選了套組後不必手動跑任何指令，匯出就帶動畫
- [ ] 沒有 `deck_animation` 的專案行為完全不變（零回歸）

### P2
- [ ] 自訂套組可儲存、可在清單中選用、可被 `apply_preset.py` 正確展開
- [ ] 輪替語法生效時效果確實不同；現有三套組行為不變

### 全體共通（新增，2026-08-12）
- [ ] **每個匯出的 .pptx 都要過兩道閘門**：
      `svg_quality_checker.py --stage final`（幾何估算）
      ＋ `python scripts/visual_check.py <匯出檔>`（LibreOffice 真實渲染逐頁 PNG）
      **後者要實際看圖**確認無跑版／擁擠／重疊——checker 對真實字型渲染是盲的
- [ ] 新增的 UI 字串一律四語言（en/ja/zh/zh-TW）
- [ ] `python scripts/check_zhtw.py` 仍全過
- [ ] patch 產生方式：工作區已有階段 1、3 的改動，必須用臨時索引重建基準樹來分離
      （階段 3 已驗證的做法：`git stash create` 取當前樹 → 臨時 index `read-tree HEAD` +
      `apply --cached` 既有 patches → `write-tree` 得基準 → `git diff 基準 當前`）
- [ ] 更新 `engine.lock` 的 `patched_files` 與 `patches` 說明（追加，不覆蓋）

## 禁止事項

- **不要為了省事重寫引擎流程**——patch 越小，未來合併越容易
- 每個新增的 patched file 都要在 `engine.lock` 說明「為什麼覆蓋層做不到」
- 不要破壞既有全量流程——單頁是額外路徑，不是取代
- 不要動階段 1、3 的既有 patch 內容

## 環境

Windows，用 `python` 不是 `python3`。檔案 UTF-8 無 BOM。測試專案用完刪除。
5050 埠可能被佔用，測試用其他埠。

## 實測數字

全量重跑：`（待填）`　單頁重生成：`（待填）`
