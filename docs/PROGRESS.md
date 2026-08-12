# shiftdeck 進度

> 最後更新：2026-08-12 10:35
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
| 1 繁中化 | ✅ 完成並驗收 | `6bc3724` |
| 2 頁型庫 | ✅ 完成並驗收 | `a56abd7` |
| 3 動畫選擇器 | ✅ 完成並提交 | `85504af` |
| 4 單頁重生成 | ✅ P0／P1／P2 全部完成並驗收 | `4b65418` |

> commit SHA 於 2026-08-12 因改寫作者信箱而全部更換過一輪，本表已同步更新。
> 若在舊筆記裡看到對不上的 SHA，以本表為準。

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


### 階段 4（單頁重生成 ＋ 換頁型 ＋ 套組自動套用）

實跑驗證，全部通過。逐項見 `handoff/stage4-single-page.md` 的驗收清單。

- **兩次真實重生成**：`04_flow_4.svg` 流程圖 → 6 指標 KPI 儀表板；`01_comparison.svg`
  沿用現有版面重畫。每次都逐檔比對 hash ＋ `mtime_ns`：**其他頁的 `svg_output/`、
  `svg_final/` 逐 byte 相同且 mtime 未變**，解壓 .pptx 比對 slide XML 也逐檔相同
- **端到端 26%**（門檻 1/3）。AI 重畫一頁實測 66s（09:53:25 → 09:54:31）；
  全量重跑要重畫 4 頁。機械管線分項與「單頁路徑反而慢 0.94s」的原因見交接文件
- **`--pages` 的實測價值**：20 頁每頁一張 2400×1350 PNG 的專案，全量 finalize 3.007s
  vs 增量 0.768s（3.9×），且兩者產出的 `svg_final/` 20 檔逐 byte 相同。純文字專案
  上則毫無差別（全被直譯器啟動時間吃掉）——這是誠實的邊界
- **P1 打中的正是回報的坑**：確認頁只能寫出 defaults-only 的 sidecar（0 列動畫），
  匯出時自動升級成 4 頁完整設定，.pptx 內含 25 列原生動畫，全程零手動指令
- **P2 零回歸用 git 對照證明**：從 `HEAD` 取出階段 3 的 `shiftdeck_animations.py`
  實跑，三個內建套組的展開結果與新版逐鍵相同（professional 25 列／lively 28 列／
  minimal 0 列）
- **覆蓋層拿掉就退回上游**：把 `overlay/` 改名後，編輯器照常啟動、新 API 全回
  `available:false`／404、匯出與 finalize 都正常且不吐任何 shiftdeck 訊息
- **兩道閘門**：`svg_quality_checker --stage final` 4/4 頁 0 error 0 warning；
  `visual_check.py` 逐頁 PNG **四頁都實際看過**，無跑版／擁擠／重疊
- `check_zhtw.py` 18 項全過（新增 22 個 UI 字串 × 4 語言，zh-TW 鍵數 105 → 133）

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

### 階段 4（單頁重生成＋動畫客製化）

P0/P1/P2 全部完成。獨立驗證（非採信 agent 自述）：

- **patch 疊加**：三個 patch 從乾淨 HEAD 依序套用後 tree SHA `98ca7361` 與工作區**完全相同**
  → 覆蓋層架構健全，上游更新時換掉 `vendor/` 重套即可
- **換頁型實測**：流程圖頁換成 KPI 儀表板，內容被重新填入（非只套骨架），LibreOffice 渲染乾淨
- **耗時**：全量 267s vs 單頁 70s＝**26%**，低於 1/3 門檻

**agent 誠實回報的反直覺發現**（值得記住）：4 頁純文字專案上，單頁路徑的**機械部分反而慢 0.94 秒**
——多出來的是那道單頁品質檢查。省下的 100% 來自 AI 只重畫一頁。原因：(1) 匯出必須全量，
引擎釋出閘門要比對 `svg_output/` 全體指紋；(2) 純文字專案 finalize 幾乎全是直譯器啟動時間。
`--pages` 的價值要在有圖的專案才顯現：20 頁每頁掛 2400×1350 PNG，全量 3.007s vs 增量 0.768s（3.9×）。

### 已知行為：換頁型後檔名不變

`04_flow_4.svg` 換成 KPI 後檔名不改。**這是刻意的**——檔名是 `animations.json` 的 slide key，
也是品質檢查頁面名冊的鍵，改名要同步搬動兩處。目前判斷維持不改（降低耦合風險），
若日後覺得困擾，再做「重新命名」功能並連帶搬移 sidecar 條目。

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
   `verify/pagetypes_四個頁型.pptx`（與 `_v2` 版本）
8. 流程圖 5／6 節點佈局未實跑（3／4／7 已驗證），首次使用時看一眼
9. 頁型縮圖尚未產出 PNG；若階段 4 選擇器需要點陣圖，要先決定 rasteriser

### 階段 3
10. **在 PowerPoint 開啟四份測試 .pptx**，確認動畫真的照設定播放（agent 只能驗到 XML 節點存在且結構正確，驗不到 PowerPoint 的實際觀感）。資料夾：`verify/`，
    內含 `stage3_professional.pptx`／`stage3_lively.pptx`／`stage3_minimal.pptx`／`stage3_none.pptx` 與各自的 `*.animations.json`。**`none` 那份是回歸對照組**，動畫窗格應該完全是空的。
11. **瀏覽器預覽與 PowerPoint 的方向感是否一致**——`entrance_fly` 的 `direction` 指的是「從哪個邊進來」，`entrance_wipe` 指的是「擦除掃過的方向」，兩者語意不同但共用同一組上／右／下／左標籤。預覽是唯一的消歧手段，值得人眼比對一次
12. 動畫面板在右側欄的**版面是否過擠**（效果列有 2 個下拉＋2 個按鈕，繁中標籤比英文長）
13. `entrance_split` 的 `_in` / `_out` 在瀏覽器預覽裡是同一個動作（單一 `clip-path` 無法表達兩段式揭示）；匯出的 PPTX 是正確的，只有預覽是近似

### 階段 4（agent 只驗到 API 與檔案，驗不到版面觀感）

> 產物留在 `verify/stage4/`：`stage4_single_page_regen.pptx`（兩次單頁重生成後的成品）、
> `slide_01..04.png`（LibreOffice 實際渲染，agent 已逐張看過）、
> `current.json` / `regen_request.json` / `regen_last_run.json`（執行期狀態檔範例）。
> 測試專案本身已依規定刪除。

14. **頁型挑選面板長什麼樣**——右欄新增一塊「頁型」，預設只有一行（頁名 ＋「換頁型」鈕），
    按下去才展開 2 欄縮圖格。要確認：(a) 4 個 `skeleton.svg` 縮圖在右欄寬度下看得清楚、
    認得出版面差異；(b)「維持現有版面」那張橫跨兩欄的卡片不突兀；(c) 選中的藍框明顯
15. **右欄會不會太擠**——這是階段 3 的第 12 項的延續。現在同一欄裡有：頁型面板、
    選取元素、動畫面板（又多了一列「套組另存」的兩個輸入框 ＋ 按鈕）、標註、動作鈕。
    繁中標籤比英文長，**四種語言都要看一次**
16. **送出重畫請求之後的引導夠不夠清楚**——按鈕按下去只會存一個 json，UI 顯示
    「請求已存好。回到對話說「重畫這一頁」」。要確認使用者看得懂這是「去跟 AI 講」
    而不是「系統會自己動」
17. **`04_flow_4.svg` 這個檔名**——它現在的內容是 KPI 儀表板。換頁型不改檔名是刻意的
    （改名會動到 `animations.json` 的 slide key 與品質檢查的頁面名冊），但使用者可能覺得怪。
    **需要你定奪**：要不要提供「換頁型時一併改檔名」的選項
18. **自訂套組存檔後的清單顯示**——存成 `my-deck` 之後，確認頁與編輯器的套組下拉
    應該多一項並標「（自訂）」。確認頁那邊 agent 沒有實跑過（只驗了編輯器端）


## E 區決策（2026-08-12 使用者裁定：全部照建議）

| 項目 | 裁定 | 狀態 |
|---|---|---|
| E1 送上游 PR | ✅ 授權 | ✅ **已送出**：[PR #259](https://github.com/hugohe3/ppt-master/pull/259)、[Issue #258](https://github.com/hugohe3/ppt-master/issues/258) |
| E2 頁型縮圖 | 用 SVG，不轉 PNG | ✅ 已寫入階段 4 交接文件 |
| E3 推 GitHub | 等階段 4 完成 | ⏳ 待執行 |
| E4 `entrance_split` 預覽落差 | 保留，面板已有說明 | ✅ 無需動作 |
| E5 套組自動套用 | 自動化 | ✅ 已列為階段 4 的 P1 |
| E6 伺服器端繁中缺口 | 補，併入同一個 PR | ✅ 已補（併進 `01-zh-tw-locale.patch`，真實 HTTP 驗過 409→200） |

### 上游 PR（2026-08-12 已送出）

| 項目 | 連結 |
|---|---|
| PR | https://github.com/hugohe3/ppt-master/pull/259 |
| Issue（先開，PR 連過去） | https://github.com/hugohe3/ppt-master/issues/258 |
| fork ／ branch | `WEIYIN-11/ppt-master` ／ `feat/zh-tw-locale`（commit `d2fa67f`，基準 `ec824ae`） |

GitHub 上核對過：**6 個檔案、482 增 35 刪**，與 `01-zh-tw-locale.patch` 完全一致。
**階段 2／3／4 的差異化功能一個都沒混進去**——`finalize_svg.py`、`svg_to_pptx.py`、
`svg_editor/server.py`、`overlay/` 全部不在變更清單裡。

**先開 issue 的原因**：上游 `CONTRIBUTING.md` 明訂翻譯類與新功能要先開 issue 討論，
「Not a fit」清單直接列了未經討論的純翻譯，新增語言又落在「may be closed without
detailed review」。所以 issue 先講來意＋附 compare 連結，PR 內文第一行連回 issue，
並主動提「若只想收那一行 server.py 的 bug fix，說一聲就把其餘拿掉」。
**這個 PR 被關掉也不影響 shiftdeck**——程式碼在 `overlay/patches/` 裡本來就能用。

逐項交接見 [`handoff/stage1-i18n.md`](handoff/stage1-i18n.md) 的「PR」段（含合併後的清理步驟）。


## 技術發現（已寫入 contract）

1. **多行文字必須用「全 `<tspan>`」形式，第一行 `dy="0"`**。混寫「直接文字 + 定位 tspan」會讓 checker 的 `_positioned_text_lines` 直接 return None——**靜默失去版面溢出檢查**。這是規範文字與驗證器行為的真實落差。
2. **未宣告字級在同一份 deck 出現超過 2 次是 error 而非 warning**。頁型用到的字級必須寫進 `spec_lock.md ## typography`。
3. **`animations.json` 頂層只認 `version` / `defaults` / `slides`**，多一個 key 就驗證失敗——所以套組 id 不能存在 sidecar 裡，改存 `confirm_ui/result.json` 的 `deck_animation.preset`。
4. **`defaults.animation.effect: "none"` 不會壓掉明列的 group 效果**（實測 26 列都有寫出來）。這正是精準控制的做法：只有列出來的 group 會動。
5. **`direction` 的語意隨效果族而變**：`entrance_fly` 的 `up` 是「從上方進來」（往下移動），`entrance_wipe` 的 `up` 是「往上擦除」。registry 的 `row_xml` 是唯一可信來源，不要照字面猜。
6. **上游 `_localized_text_present()` 只認 `_zh` / `_en` / `_ja`，不認 `_zh_tw`**（`confirm_ui/server.py`）。stage2 推薦檔的 `custom_candidates` 與 `design_directions` 只寫繁中會被 409 擋下。~~階段 1 沒動它是對的~~——**2026-08-12 E6 已修**，tuple 補一個 `f'{field}_zh_tw'`，併進 `01-zh-tw-locale.patch`。全樹掃過，這是整個 vendor Python 樹裡**唯一**一處寫死語言 suffix 白名單的地方（`_build_catalogs()` 的 `label_zh`/`use_en` 是英文名稱回填，走 `zh_tw → zh` fallback 本來就通）。
7. **`svg_quality_checker.py <單一 svg 檔>` 本來就能跑**，且會自己往上找到專案的 `spec_lock.md`。單頁品質檢查不需要任何 patch——階段 4 交接文件說 `--stage first-page` 是最重要的線索，但真正的線索是 CLI 一直接受單一檔案路徑。
8. **匯出有指紋閘門**：`svg_to_pptx` 會比對 `svg_output/` 全體的指紋與 `validation/svg_quality_report.json`，對不上就拒絕匯出。所以「單頁重生成」永遠要在匯出前補跑一次全份 final 檢查（0.9s）。這不是可以優化掉的東西，是釋出閘門。
9. **`finalize_svg.py` 的產物發布是整個目錄原子替換**，但候選目錄是 `copytree`（＝`copy2`）自 `svg_output/`，所以沒被任何步驟改到的頁會保留原 mtime。純文字專案上全量 finalize 也不會重新蓋章 mtime——`--pages` 真正買到的是**時間**，不是 mtime 穩定性。
10. **`animations.json` 的 `slides` 鍵是「已展開」的可靠訊號**。確認頁只能寫 `version`+`defaults`（發現 3），所以「有 preset 但沒有 slides」＝使用者選了套組卻還沒展開，這正是 P1 唯一該出手的時機；有 `slides` 就一律不碰，手動微調永遠不會被蓋掉。

## 已修正的坑

`engine.lock` 原鎖 `b6ed57c0`（main HEAD），但 `v4.5.0` tag 實際指向 `ec824aec`，兩版 `confirm_ui/app.js` 有實質差異會使行號失準。已改鎖正式 tag（commit `bcda74e`）。

## 階段 3 的檔案地圖

| 檔案 | 角色 |
|---|---|
| `overlay/animations/presets.json` | 三套組配置＋元素分類規則＋每類 8 個常用效果的四語標籤（**唯一資料來源**） |
| `overlay/animations/shiftdeck_animations.py` | 共用函式庫：讀套組、展開成 sidecar、用引擎自己的驗證器把關、寫檔 |
| `overlay/animations/apply_preset.py` | CLI：`--preset <id>` 或 `--from-result`，把套組展開成完整的每頁每元素設定 |
| `overlay/patches/03-animation-selector.patch` | 引擎端接線（1,505 行，基準＝01 patch 套用後的樹） |

**vendor 端只有接線**：兩個 `server.py` 各加一段「往上找 `overlay/animations/`」的 bootstrap 與新 API，找不到就整組功能自動關閉、行為退回上游（已實測：把 overlay 改名後 `/api/animations` 回 `available:false`、`/api/animation-presets` 回空清單，兩個伺服器都正常啟動）。

## 階段 4 的檔案地圖

| 檔案 | 角色 |
|---|---|
| `overlay/pagetypes/catalog.json` | 頁型清單＋四語標籤＋彈性範圍（**唯一資料來源**；新增頁型＝一個資料夾＋這裡一筆，不必改程式） |
| `overlay/regen/shiftdeck_regen.py` | 共用函式庫：選取狀態通道、頁型目錄與縮圖、重生成請求、給 AI 的 briefing |
| `overlay/regen/regen_page.py` | CLI：`--show` 讀請求／`--request`＋`--page` 跑快路徑／`--full` 量測基準 |
| `overlay/animations/user/README.md` | 自訂套組的格式、輪替語法、要不要進版控 |
| `overlay/patches/04-single-page-regen.patch` | 引擎端接線（1,015 行，基準＝01→03 依序套用後的樹） |

**專案內的執行期檔案**（都在上游既有的 `<專案>/live_preview/` 底下）：
`current.json`（現在選了哪一頁／哪個元素）、`regen_request.json`（待重畫的請求）、
`regen_last_run.json`（上次快路徑的分步耗時）、`regen_history.jsonl`（請求生命週期）。

**單頁重生成的實際流程**：使用者在預覽裡選頁型 → 按「請 AI 重畫這一頁」（伺服器只
記錄請求，不重畫）→ 回到對話 → AI 跑 `regen_page.py --show` 拿到頁面路徑、契約、
骨架與備註 → **只重寫那一支 SVG** → 跑 `regen_page.py --request` 完成單頁檢查、
增量 finalize、匯出，並把請求標記為完成。

## 發布準備（2026-08-12）

開源專案的基本件已補齊：

| 檔案 | 內容 |
|---|---|
| `docs/usage.md` | 使用者視角完整流程（README 原本就連過去，檔案先前不存在） |
| `README.md` | 對齊四階段實況：動畫套組、`visual_check.py`、單頁重生成的實測數字與誠實邊界 |
| `CONTRIBUTING.md` | 覆蓋層架構、`vendor/` 不可改的三個實際後果、patch 產生與兩道交叉驗證 |
| `.github/ISSUE_TEMPLATE/` | 錯誤回報／功能建議／config（引擎本身的問題導向上游） |
| `AGENTS.md` ＋ `CLAUDE.md` | **新發現的缺口**：repo 根目錄沒有 agent 進入點，AI 工具打開 shiftdeck 資料夾時找不到 `vendor/ppt-master/skills/ppt-master/SKILL.md`（引擎自己的 repo 靠根目錄 `AGENTS.md` 指路，shiftdeck 少了這一份）。同時明訂專案要建在根目錄 `projects/`——建進 `vendor/` 會在下次 `setup.py` 重抓時被 `rmtree` 刪掉 |

**CONTRIBUTING 的 patch 產生法已實跑驗證**：用臨時索引（`GIT_INDEX_FILE`）套 01→03 重建基準樹
`f30ff4a3`，再 `git diff` 工作區，產出的 patch 與 `04-single-page-regen.patch` **逐 byte 相同**。
全部 patch 疊加的樹 SHA 亦重現為 `98ca7361`，與 PROGRESS 既有紀錄一致。
**E6 併入後樹 SHA 改為 `78bc80bc`**（01 多了 server.py 一行），01→03→04 依序套用仍乾淨，
與工作區逐 byte 相同——E6 插入的那行沒有讓 03／04 的 hunk 失準。

### E6：伺服器端繁中缺口（已修並驗證）

`_localized_text_present()` 的 suffix 白名單補上 `_zh_tw`，**改動一行**。逐項見
[`handoff/stage1-i18n.md`](handoff/stage1-i18n.md) 的「E6」段。要點：

- **真實 HTTP 重現**（非推論）：同一份 stage2 fixture（文案只寫 `*_zh_tw`）、同一支伺服器，
  只差那一行——上游 v4.5.0 回 `409 custom_candidates.mode requires non-empty localized name`，
  補完回 `200` 並帶著繁中文案
- **純加法的實證**：11 種輸入形態逐一比對新舊實作，只有「只寫 `_zh_tw`」從 `False` 變 `True`
- **PR 草稿的每一項宣稱都機械驗過**：`en`/`ja`/`zh` 三個 `MESSAGES` 物件、20 列內嵌對照表、
  catalogs 去掉 `*_zh_tw` 後的 49,435 bytes，全部與 v4.5.0 逐 byte 相同；兩個 `index.html`
  各只多一行、零刪除；`check_zhtw.py` 對 PR 分支（不含階段 3/4）18 項全過，鍵數 176／73／172

## 下一步

1. 人工驗收：階段 1（1–6）、階段 2（7–9）、階段 3（10–13）、階段 4（14–18）
2. 第 17 項需要你定奪（換頁型要不要一併改檔名）
3. ~~E1／E6 送上游 PR~~ ✅ 已送出（[PR #259](https://github.com/hugohe3/ppt-master/pull/259)）——
   接下來只要等維護者回覆；若他只想收 server.py 那一行，PR 內文已主動提出可縮減
4. E3 推 GitHub（shiftdeck 自己的 repo，尚未執行）
