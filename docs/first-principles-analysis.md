# 簡報工作流第一性原理分析：ppt-master × open-slide 逆向工程

> 2026-08-11 · 基於實跑 ppt-master 完整管線（14 頁 deck）+ open-slide 原始碼深度探索
> 分析對象：`ppt-master`、`open-slide`、`openslide-ppt-skill`（⚠️ 已確認損壞，見附錄）三份本機原始碼

---

## 一、第一性原理：一個 AI 簡報工作流不可約的六件事

把「AI 做簡報」拆到底，任何工作流都必須回答這六個 job：

| Job | 本質問題 |
|---|---|
| J1 內容決策 | 受眾是誰、要改變他什麼、怎麼分頁 |
| J2 設計系統 | 色彩/字級/版面語言怎麼鎖定且跨頁一致 |
| J3 頁面實現 | 用什麼「中間語言（IR）」讓 AI 把內容+設計寫成頁 |
| J4 品質驗證 | AI 看不到自己畫的東西——怎麼保證不爆版、不醜、事實正確 |
| J5 交付格式 | .pptx？網頁？PDF？影片？接手的人能不能改 |
| J6 迭代 | 「改這個標題」的最小成本是多少 |

**核心洞見：兩個專案其實是同一個架構的兩種實例——都是「編譯器」思路。**
AI 不直接產出交付物，而是寫一種它已經很熟練的受限中間語言，由工具鏈編譯到目標格式。差別只在 IR 與編譯目標的選擇，而這個選擇決定了各自的一切強弱。

```
ppt-master:  受限 SVG（封閉白名單）──編譯──▶ 原生 DrawingML .pptx
open-slide:  React component（1920×1080）──runtime──▶ 瀏覽器 deck（PDF/圖片式 PPTX 為降級匯出）
```

---

## 二、逐 Job 對比拆解

### J1 內容決策

| | ppt-master | open-slide |
|---|---|---|
| 機制 | 兩階段 Confirm UI（溝通契約+模板 → 完整方案三選一），產出 design_spec.md §IX 逐頁 brief（含 Audience move、核心訊息、完整措辭） | `create-slide` skill 用 AskUserQuestion 問四題（美學/頁數/密度/動態），然後直接寫 |
| 評價 | 最重也最完整：每頁被迫回答「這頁改變觀眾什麼」，這是它成品敘事品質的真正來源 | 輕快但淺，內容策略基本靠模型自由發揮 |

**判決**：ppt-master 的「溝通契約 → 逐頁 Audience move」是全場最有價值的資產，值得原樣保留。

### J2 設計系統

| | ppt-master | open-slide |
|---|---|---|
| 機制 | design_spec（人讀）+ spec_lock（機讀錨點：六角色色盤、字級角色±2px、圖示庫、頁面節奏），Executor 每 5 頁重讀 lock 抗漂移 | per-slide `design` const（palette/fonts/typeScale/radius）→ CSS vars；theme = markdown 文件 + demo.tsx 成對 |
| 評價 | 雙 artifact 分離「人類決策」與「機器錨點」，是抗長 context 漂移的正解 | token shape 極小但即時（Design 面板拖曳直接 AST 寫回原始碼） |

**判決**：ppt-master 的 lock 機制 + open-slide 的「面板改 token 即時寫回」合起來才完整。

### J3 頁面實現（IR 選擇）

| 維度 | 受限 SVG（ppt-master） | React/JSX（open-slide） |
|---|---|---|
| AI 熟練度 | 高 | 極高 |
| 幾何可驗證性 | **顯式座標，可靜態分析** | 隱式（layout 由瀏覽器算），無法靜態驗證 |
| 表達力 | 受白名單限制（無 mask/blur/blend） | 全部 web 能力（動畫、互動、Magic Move） |
| 可編譯到 PPTX | ✅ 每個元素 → 原生 DrawingML 物件 | ❌ 只能截圖貼滿版 |
| 單頁成本 | ~100-200 行 | 實測 1000-1800 行/頁 |

**判決**：**要交付 .pptx，SVG IR 是唯一正解**（幾何顯式 → 可靜態驗證 → 可確定性編譯）。JSX 的優勢全在「交付物就是網頁」的場景。

### J4 品質驗證 ⟵ 兩者共同的阿基里斯腱

| | ppt-master | open-slide |
|---|---|---|
| 防爆版 | **可執行的靜態檢查器**：文字範圍=y−0.85f..y+0.35f 的字形數學，超模組界 >5% 直接 fail；封閉語法白名單 fail-closed | **31 行 prompt 教模型心算**垂直預算；超出 1080px 靜默裁切，零偵測。scaffold 專案連 tsc/linter 都不裝 |
| 防「醜」 | visual-review stage 存在但 **opt-in、預設不跑** | 15 項自檢 checklist（自評，非驗證） |

**判決**：ppt-master 證明了「**驗證器 > prompt 紀律**」——同一條規則，寫成 checker 就是保證，寫進 prompt 就是祈禱。但兩者都缺最後一塊：**渲染回饋**。AI 全程盲畫，數學只能抓溢界，抓不到擁擠、失衡、對比不足。

### J5 交付格式

| 目標 | ppt-master | open-slide |
|---|---|---|
| 可編輯 .pptx | ✅ 原生物件+母版+轉場+旁白 | ❌ 圖片貼滿版 |
| 網頁分享 | ❌ | ✅ 純靜態 dist/，任何主機可放 |
| PDF | 間接 | ✅ 瀏覽器端，處理過投影機坑 |
| 接手者門檻 | 會 PowerPoint 就能改 | 需要裝 node + pnpm + dev server |

**判決**：完全互補。「寄給別人改」的辦公室世界 → ppt-master；「傳個連結」的網路世界 → open-slide。

### J6 迭代 ⟵ open-slide 的皇冠

open-slide 的閉環是全場最佳工程：

1. 瀏覽器按 `i` 開 inspector → 點任何元素 → 面板直接改字/色/字級，**Babel AST 精準寫回原始碼**
2. 改不動的 → 留言存成原始碼內 `@slide-comment` marker → `/apply-comments` 讓 agent 撈出逐一套用
3. dev server 把「使用者現在指著哪」寫進 `current.json` → agent 把「這個標題」解析成精確的檔案+行號

ppt-master 的 svg_editor 有前兩步的雛形（拖拽改+註解），但沒有第三步的「選取狀態通道」，且迭代單位偏粗（重寫區域→全量重匯出）。

**判決**：「指著螢幕說話」的通道設計必抄。

---

## 三、成本結構（實測）

| 成本 | ppt-master | open-slide |
|---|---|---|
| 生成前規範載入 | **15 份文件、約 5,100 行**（實跑本次 deck 的真實數字） | slide-authoring 家族 1,307 行 |
| 全語料 | 212 個 md、約 29.4 萬字 | 5 個內建 skill |
| 單頁產出 | ~100-200 行 SVG | 1,000-1,800 行 TSX |
| 人工打斷點 | 2 次確認（可用 Quick 歸零） | 1 次四題確認 |

ppt-master 把大量「本可寫成工具」的規則放在 prompt 裡維持紀律，這是它 token 稅的主因——但它同時也是兩者中唯一真的把部分規則工具化（checker）的。方向對，做得不夠徹底。

---

## 四、更好的工作流：藍圖

### 設計原則（從以上判決導出）

1. **IR 用受限 SVG**——幾何顯式才可驗證、才可編譯到原生 PPTX；web 交付是編譯 target 之一，不是架構
2. **能寫成 checker 的規則，一律不放 prompt**——prompt 只留品味，硬規則全部工具化
3. **補上渲染回饋閉環**——AI 必須「看到」自己畫的頁再放行
4. **迭代最小單位是元素，不是頁**——選取通道 + 註解 marker
5. **內容/設計/頁面/目標 四層解耦**——同一份規劃可編譯出 pptx / web / pdf / 影片

### 架構

```
L0 內容契約   brief（受眾/意圖/每頁一行 Audience move）      ← 人審一次，唯一必要打斷
L1 設計錨點   design lock（六角色色盤/字級角色/圖示庫/節奏）  ← 可從品牌工作區直接繼承
L2 頁面 IR    每頁一個受限 SVG（沿用 ppt-master 白名單）
L3 驗證閘門   靜態 checker（幾何/語法）＋ 渲染截圖 → vision 自檢（新增，抓「醜」）
L4 編譯目標   → 原生 .pptx ｜ → 靜態 web deck（借 open-slide 播放層）｜ → PDF ｜ → 旁白影片
L5 迭代通道   瀏覽器點選 → 選取狀態檔 → AI 精準改該元素 → 只重驗證該頁
```

### 落地路徑（不重造輪子，改造 ppt-master）

ppt-master 已擁有 L0-L4 的 80%。三個最高 ROI 的改造，按順序做：

**Phase 1 — 視覺自檢預設化（最高 ROI，一天內可做）**
ppt-master 的 `visual-review` stage 已存在但 opt-in。改造：final gate 通過後，自動把 `svg_final/` 逐頁截圖餵 vision 過一輪「擁擠/失衡/對比/對齊」檢查，發現問題自動修復再重驗。這一步同時是對 open-slide 路線的降維打擊——它連 opt-in 的都沒有。

**Phase 2 — 個人精簡執行卡（把 5,100 行壓到 ~600 行）**
既然 checker 已兜底所有硬錯誤，prompt 規範可以大砍。做一份個人版 skill：保留「溝通契約→逐頁 Audience move」的規劃精華 + 視覺品味要點，硬規則全部刪掉（讓 checker 報錯再修，比預防性讀 5,000 行便宜得多）。搭配 Quick 模式跑日常，正式場合才走完整確認。

**Phase 3 — 移植 open-slide 迭代通道**
給 ppt-master 的 live preview 補一個 `current.json` 式選取狀態檔：使用者在預覽裡點著哪個元素，AI 就知道「這個」指什麼；註解迴路改成元素級精準編輯 + 單頁重驗，不再全量重匯出。

### 場景分流（現在就能執行的使用策略）

| 場景 | 用什麼 |
|---|---|
| 要交 .pptx 給別人繼續改（客戶、內訓、正式提案） | ppt-master（Default 或 Quick） |
| 線上分享連結、教學展示、需要 web 動畫 | open-slide 本體＋官方內建 skill（`create-slide`） |
| 品牌一致性 | 先用 ppt-master `create-template` 建一次 coolkid 品牌工作區，之後每份 deck 引用 |
| ~~openslide-ppt-skill~~ | **不要用**，見附錄 |

---

## 附錄：openslide-ppt-skill 屍檢報告

`torns/openslide-ppt-skill`（單一 commit，2026-05-12）是照著「對 open-slide 的想像」寫的，與真實 API 不相容：

- 它 import 的 `Slide` 元件在 `@open-slide/core` 的 export 清單中**不存在**（真實契約是 `export default [Cover, Body] satisfies Page[]`）
- 用 Tailwind class，但使用者專案不含 Tailwind（框架要求絕對 px inline style）
- 字級指引「標題 48px+」與 1920 畫布的真實型階（Hero 140-200px）差一個量級
- 完全沒提 1080px 垂直預算、design const、inspector 循環——open-slide 最有價值的部分全數丟失

**教訓（通用）**：把設計約束放在 prompt 而非型別系統/驗證器裡的生態，任何人都可以寫一個「表面看起來對」的 wrapper 而無人察覺它對著不存在的 API 編譯。這正是原則 2（驗證器 > prompt）的反面教材。
