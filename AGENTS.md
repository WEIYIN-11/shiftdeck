# AGENTS.md

AI agent 的進入點。使用者在這個資料夾裡要求做簡報時，先讀這一份。

## 必讀

**做任何簡報任務前，你 MUST 先讀 [`vendor/ppt-master/skills/ppt-master/SKILL.md`](vendor/ppt-master/skills/ppt-master/SKILL.md)。**
它擁有全域執行紀律與路由選擇；路由選定後，該路由的 runtime authority 擁有它自己的步驟與閘門。

引擎尚未安裝（`vendor/` 不存在）時，先告訴使用者跑 `python scripts/setup.py`，不要試圖繞過。

## shiftdeck 是什麼

疊在 ppt-master 上的覆蓋層，加了四件事：職場頁型庫、動畫選擇器、單頁重生成、繁體中文介面。
引擎的所有既有行為不變——`overlay/` 拿掉就乾淨退回上游。

## 硬規則

1. **專案建在 repo 根目錄的 `projects/`**，不是 `vendor/ppt-master/projects/`。
   引擎的 `project_manager.py init` 以 CWD 推導 `projects/`，所以指令的工作目錄要是 repo 根目錄，
   或明確帶 `--dir`。**放進 `vendor/` 的專案會在下次 `setup.py` 重抓引擎時被整個刪掉。**
2. **不要直接改 `vendor/`**。它不進版控、會被 `setup.py` 整個 `rmtree` 重抓。
   引擎端的改動一律走 `overlay/patches/`，做法見 [CONTRIBUTING.md](CONTRIBUTING.md)。
3. **新增的 UI 字串一律四語言**（`en` / `ja` / `zh` / `zh-TW`），然後跑 `python scripts/check_zhtw.py`（18 項要全過）。
4. **每個匯出物要過兩道閘門**：引擎的 `svg_quality_checker --stage final`（幾何）
   ＋ `python scripts/visual_check.py <匯出檔>`（LibreOffice 真實渲染）。
   **第二道產出的 PNG 要真的逐頁看過**——checker 對跑版頁會回報 0 errors。

## 覆蓋層功能與觸發時機

| 使用者說 | 你要做的事 |
|---|---|
| 「重畫這一頁」「換頁型」 | `python overlay/regen/regen_page.py projects/<專案> --show` 取得目標頁、契約與骨架 → **只重寫那一支 SVG** → `--request` 跑快路徑 |
| 「第 N 頁用 SWOT／KPI／流程圖／對比」 | 讀 `overlay/pagetypes/<id>/contract.md` 與 `skeleton.svg`，依契約重畫 |
| 想要動畫 | 確認頁的套組選擇會自動在匯出時展開，**不必手動跑 `apply_preset.py`** |
| 要產生 `spec_lock.md` | 跑 `python overlay/scaffold/spec_lock.py <專案>`，**不要用引擎的 `scaffold-lock`**——理由見下方 |

## 產生 spec_lock.md 用覆蓋層那支

```bash
python overlay/scaffold/spec_lock.py projects/<專案>
```

引擎的 `project_manager.py scaffold-lock` 給的是引擎通用的最小集合：`typography`
只有 `body` 與 `title`、`colors` 只有四個鍵。那對上游沒錯，它不知道 shiftdeck 加了
頁型庫；但頁型骨架實際用到**五個字級（54/40/24/18/14）與八個色角色**，照引擎的
scaffold 填完必定撞上：

```
undeclared font-size 24 (8 occurrences) exceeds the sparse-display limit of 2
```

2026-08-15 的四個獨立頁型測試全部踩到這一個坑。覆蓋層那支會先讓引擎產生基底
（schema 跟著上游走），再掃 `overlay/pagetypes/*/skeleton.svg` 把真正需要的字級與
色角色補上，並依 `svg_output/` 的實際檔案列出 `page_rhythm`。新增頁型時它自動跟上，
不必回頭改腳本。

**寫 `## colors` 時不要加行內註解**：引擎的 `load_theme_color_spec` 會把 `:` 後面
整段丟給 `parse_hex_color`，一個註解就讓那行被靜默跳過；全部跳過的話品質閘門會回
報 `theme contract is missing: colors`。
| 「值班」「我要在瀏覽器上操作」「開主控台」 | 見下方〈主控台值班模式〉：跑 `agent.py wait` 等瀏覽器送來的請求，不要叫使用者回對話框打字 |

## 主控台值班模式

`overlay/console/` 讓使用者不必回對話框打字：瀏覽器按鈕寫一筆請求進收件匣，
你用 `agent.py wait` 等到它。使用者說要在瀏覽器操作時，走這個迴圈：

```bash
python overlay/console/server.py              # 一次就好，開著不用關
python overlay/console/agent.py wait          # 你這一輪就停在這裡等
```

`wait` 回來後你會拿到一筆 JSON（已自動 claim）。依 `kind` 處理：

| kind | 你要做的事 |
|---|---|
| `new_deck` | 用 payload 的主題／受眾／頁數／材料走完整 generate 流程；材料在 `.shiftdeck/materials/<id>/`，複製進專案 `sources/`，不要動原檔 |
| `regen_page` | 等同「重畫這一頁」，走 `regen_page.py --show` → 重寫該支 SVG → `--request` |
| `apply_edits` | 套用預覽編輯器裡待處理的修改 |
| `export` | 跑 finalize → 品質閘門 → `svg_to_pptx.py` |

**處理途中要回報**，否則使用者只看得到轉圈：

```bash
python overlay/console/agent.py status "正在重畫第 3 頁" --progress 0.4
python overlay/console/agent.py done <request-id> --note "已換成對比頁"
```

處理完**立刻再跑一次 `wait`**，讓使用者可以連續操作。

**誠實的邊界**：`wait` 會佔住你這一輪，且有 timeout。時間到之後在使用者再次
說話之前，請求只會排在收件匣裡沒人處理——主控台會顯示「等待 agent 接手」而
不是假裝在跑。這是回合制工具的限制，不要假裝繞得過去。每一輪對話開頭可以用
`agent.py peek` 順手查有沒有積壓的請求。

**單頁重生成的重點是「只重寫那一支 SVG」**——其他頁的檔案一個 byte 都不要動。
匯出仍是全量的（引擎的釋出閘門要求整份有一份通過的品質報告），這是刻意的，不要繞過。

## 寫頁型 SVG 時

- 多行文字必須用**全 `<tspan>`** 形式，第一行 `dy="0"`。混寫「直接文字 + 定位 tspan」會讓
  checker 靜默失去版面溢出檢查（`_positioned_text_lines` 直接 return None）。
- 未宣告的字級在同一份 deck 出現超過 2 次是 **error 不是 warning**；頁型用到的字級要寫進 `spec_lock.md ## typography`。
- **跨軟體字型度量餘裕**：LibreOffice 對 CJK＋拉丁混排的字寬估算比 PowerPoint 寬 7–10%，
  會強制重斷行。契約裡的字數上限已據此下修，照著寫。

## 相關文件

| 檔案 | 內容 |
|---|---|
| [`docs/usage.md`](docs/usage.md) | 使用者視角的完整流程 |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | 每個功能的實測數字、技術發現、誠實邊界、待辦 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 覆蓋層架構、patch 產生與驗證方法 |
| [`engine.lock`](engine.lock) | 鎖定的引擎版本、9 個 patched files 與各自的理由 |
