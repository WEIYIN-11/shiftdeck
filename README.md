# shiftdeck ｜簡報手排檔

**別人的 AI 簡報是自排，這個是手排——你想換檔，自己換。**

頁型用挑的、動畫用點的、單頁重做不用等全份。

> 本專案使用 [ppt-master](https://github.com/hugohe3/ppt-master)（MIT）的 SVG → 原生 PPTX 編譯引擎，
> 在其上新增：職場頁型庫、動畫選擇器、單頁重生成、繁體中文介面。
> 引擎版本鎖定於 [`engine.lock`](./engine.lock)。

---

## 這是什麼

AI 簡報工具現在都很聰明——你給材料，它給你一份完整的簡報。問題在**它決定了一切**：版面它挑、動畫它配、你想改一頁就得用文字跟它拉扯，改完還要等整份重跑。

shiftdeck 把三個選擇權還給你：

| 你想做的事 | 現在怎麼做 |
|---|---|
| 這頁我要 SWOT 版面 | 從頁型庫**挑**，不是描述給 AI 聽 |
| 這個標題要用飛入 | **點**元素選效果，即時預覽單一元素的動畫 |
| 第 5 頁重做 | 只重跑第 5 頁，不用等全份 |

底層仍然是 ppt-master 的編譯引擎，所以輸出還是**原生可編輯的 .pptx**——真正的 PowerPoint 形狀、文字框、圖表，不是一頁一張圖。

## 安裝

需要 Python 3.10+。

```bash
git clone https://github.com/<your-account>/shiftdeck.git
cd shiftdeck
python scripts/setup.py
```

`setup.py` 會取得鎖定版本的引擎並套用覆蓋層。引擎本身不進版控（14,000+ 檔案），由安裝時取得。

## 使用

在有 agent 能力的 AI 工具（Claude Code、Cursor、Codex CLI 等）裡打開本資料夾，把材料放進 `projects/`，然後在對話裡說要做什麼。詳見 [使用說明](./docs/usage.md)。

## 頁型庫

| 頁型 | 彈性 |
|---|---|
| 對比頁 | 2 欄 |
| 流程圖 | 3-7 節點 |
| SWOT | 4 象限 |
| KPI 儀表板 | 3-6 指標 |

## 架構

```
shiftdeck/
├── engine.lock      引擎版本鎖定（repo + commit）
├── overlay/         所有客製化——純加法，不改引擎
│   ├── i18n/        繁體中文字典
│   ├── pagetypes/   頁型庫（骨架 + 槽位契約）
│   ├── animations/  動畫套組
│   └── patches/     引擎修補（唯一破例：單頁重生成）
├── scripts/         安裝與套用
└── vendor/          引擎（gitignore，安裝時取得）
```

設計原則：**引擎目錄保持乾淨、可整包替換**。上游更新時只需換掉 `vendor/`，覆蓋層自動繼承。

## 授權

[MIT](./LICENSE)。第三方歸屬見 [NOTICE](./NOTICE)。
