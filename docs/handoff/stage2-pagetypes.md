# 階段 2：職場頁型庫

> 冷啟動可執行。先讀 [`../decisions.md`](../decisions.md)。
> **可與階段 1 並行**——本階段是純加法，不碰引擎既有檔案，零衝突。

## 目標

建立 4 個職場頁型，讓使用者可以「挑版面」而不是「描述給 AI 聽」。

## 形態：骨架 ＋ 槽位契約

每個頁型 = 兩個檔案：

| 檔案 | 內容 |
|---|---|
| `skeleton.svg` | 可渲染成縮圖的版面骨架，定義區塊與槽位位置 |
| `contract.md` | 給 AI 的伸縮規則：內容多寡如何調整、槽位語意、禁止事項 |

放在 `overlay/pagetypes/<name>/`。

## 四個頁型規格

| 頁型 | 目錄 | 彈性 | 可複用的引擎資產 |
|---|---|---|---|
| 對比頁 | `comparison/` | 固定 2 欄 | `templates/tables/comparison_matrix.svg`、`feature_matrix.svg` |
| SWOT | `swot/` | 固定 4 象限 | `templates/charts/matrix_2x2.svg` |
| KPI 儀表板 | `kpi-dashboard/` | **3-6 個指標**，超過建議拆頁 | `templates/charts/gauge_chart.svg`、`bullet_chart.svg`、`progress_bar_chart.svg` |
| 流程圖 | `flowchart/` | **3-7 節點** | ⚠️ 無現成資產，見下方 |

引擎資產路徑：`vendor/ppt-master/skills/ppt-master/templates/`

**流程圖是四個裡最需要新開發的**：引擎的 `references/executor-structure.md` 有一條硬規則「**no Structure catalog**」——流程圖被刻意設計成每次由 AI 即席手繪，所以每次長得都不一樣。本頁型的價值正是打破這個不確定性，但要注意不能與引擎的 Structure 決策邏輯打架（我們是提供骨架，不是註冊進它的 catalog）。

## 設計約束（必須遵守，來自引擎）

- 畫布 `viewBox="0 0 1280 720"`，安全邊距 40px
- 每個邏輯單元一個 top-level `<g id="...">`，且必須有 `data-pptx-bounds="x y width height"`
- 只能用引擎白名單內的 SVG 語法：**禁止** `mask`、`<style>`、`class`、`filter` 以外的效果、`foreignObject`、`textPath`
- 顏色用 `#RRGGBB`；骨架用語意佔位色，實際配色由專案的 `spec_lock.md` 決定
- 文字用 `<text>` ＋ 定位 `<tspan>`（同段落不可用兄弟 `<text>`）
- 完整規範：`vendor/ppt-master/skills/ppt-master/references/shared-standards-core.md`

## 接入方式（v1 範圍）

**生成前指定**（零引擎改動）：使用者在需求裡說「幫我做一頁 SWOT」，AI 規劃時讀取頁型庫並採用。做法是在 `overlay/` 提供一份給 AI 讀的頁型索引，並在 shiftdeck 的使用說明裡告訴 AI 何時查閱。

**生成後替換**屬於階段 4（需要單頁重生成），本階段**不做**。

## 驗收標準

- [ ] 4 個頁型各有 `skeleton.svg` ＋ `contract.md`
- [ ] 每個 `skeleton.svg` 單獨通過引擎的品質檢查（把骨架放進測試專案的 `svg_output/` 跑）：
      `python vendor/ppt-master/skills/ppt-master/scripts/svg_quality_checker.py <測試專案> --stage final --json`
- [ ] 實跑驗證：用 shiftdeck 生成一份包含全部 4 種頁型的測試簡報，匯出的 .pptx 在 PowerPoint 開啟正常，元素可編輯
- [ ] KPI 頁型在 3 個和 6 個指標下都不爆版；流程圖在 3 個和 7 個節點下都不爆版
- [ ] 每個頁型有縮圖（供階段 4 的選擇器使用，本階段先產出檔案即可）

## 禁止事項

- 不要改 `vendor/` 裡的任何檔案（本階段必須維持零 patch）
- 不要為了頁型去註冊引擎的 Structure catalog（那條硬規則不繞）
- 不要在骨架裡寫死配色——那是專案 lock 的職責
