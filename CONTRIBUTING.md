# 貢獻指南

歡迎。開工前只有一條規則必須先懂：**這個專案的所有改動都是「加法」**。

---

## 覆蓋層架構

shiftdeck 不是 ppt-master 的 fork，是**疊在它上面的一層**。

```
vendor/ppt-master/     上游的乾淨快照 —— 唯讀，安裝時取得，不進版控
overlay/               shiftdeck 的全部內容 —— 你的改動放這裡
engine.lock            兩者之間的契約：鎖哪一版、破例改了哪幾個檔
```

這樣做是為了一件事：**上游更新時，換掉 `vendor/` 就好，覆蓋層自動繼承。**

### `vendor/` 不可直接改

不是慣例問題，是會真的出事：

1. **會被洗掉**——`scripts/setup.py` 發現版本不符時直接 `rmtree` 整個目錄重抓。你的改動沒有備份。
2. **不進版控**——`vendor/` 在 `.gitignore` 裡。你改了，別人 clone 下來沒有。
3. **升級即失效**——沒有記錄在 patch 裡的改動，下次換引擎版本就無聲消失。

同理，**不要把任何自己的東西放進 `vendor/`**，包括測試專案。專案建在根目錄的 `projects/`。

### 決策樹：我的改動該放哪

```
能不能只加檔案到 overlay/，引擎完全不動？
├─ 可以 → 放 overlay/，收工。這是絕大多數情況
└─ 不行 → 引擎端能不能只加一段「往上找 overlay/」的接線？
    ├─ 可以 → 寫成 patch，但邏輯與資料全部住在 overlay/，
    │         vendor 端只有 bootstrap 與 API 註冊
    └─ 不行 → 停下來，把理由寫進 engine.lock 的 patches 說明再動手
```

**每一個 patched file 都是一筆未來的合併債務。** `engine.lock` 目前列了 9 個，每一筆在 `patches` 欄位都寫了「為什麼覆蓋層做不到」。加第 10 個之前，先確認你真的說得出那個理由。

### 判準：什麼叫「覆蓋層做不到」

實際採用過的兩個例子，可以拿來對照：

- **`finalize_svg.py` 加 `--pages`**：打包的步驟順序與未來新增的步驟都住在引擎裡。覆蓋層若自己重排一次呼叫順序，下次升級引擎就會**無聲走樣**——不是報錯，是產出悄悄不對。
- **`svg_to_pptx.py` 加匯出前自動展開動畫套組**：匯出是使用者與工作流直接呼叫的入口。要讓「確認頁選了套組」在標準指令下自動生效，只能掛在這個入口；改成叫 overlay 的另一支腳本，等於改掉既有流程。

反例（這些**不**構成理由）：「放 overlay 要多寫幾行」、「改引擎比較快」、「反正只有一行」。

### 退場測試

覆蓋層的健康度有一個具體的驗收方式，**加新功能時請跑一次**：

把 `overlay/` 改名，然後啟動兩個伺服器、跑一次匯出。應該要：

- 兩個伺服器都正常啟動
- 新 API 全部回 `available:false` 或 404
- 匯出與打包正常，且**不吐任何 shiftdeck 訊息**

也就是**乾淨退回上游行為**。做不到就是接線寫髒了。

---

## 怎麼產生 patch

patch 是**依序疊加**的：`01` 的基準是乾淨上游，`03` 的基準是「01 套用後」，`04` 的基準是「01→03 套用後」。所以直接 `git diff` 會把前面所有層的改動一起吐出來——必須先重建基準樹。

做法是用**臨時索引**：把前面的 patch 只套進一個丟棄式的索引檔，寫出那棵樹，再拿它跟工作區比。實際的工作區完全不動。

```bash
cd vendor/ppt-master

# 1. 用臨時索引重建基準樹（把你之前的每個 patch 依序套進去）
export GIT_INDEX_FILE=/tmp/shiftdeck-base-index
rm -f "$GIT_INDEX_FILE"
git read-tree HEAD
git apply --cached ../../overlay/patches/01-zh-tw-locale.patch
git apply --cached ../../overlay/patches/03-animation-selector.patch
BASE=$(git write-tree)
unset GIT_INDEX_FILE
echo "基準樹 $BASE"

# 2. 拿基準樹跟工作區比，只會得到你這一層的改動
git diff "$BASE" -- <你動到的檔案或目錄> > ../../overlay/patches/05-你的功能.patch
```

`-- <路徑>` 那段很重要：如果同時有別人在改 `vendor/` 的其他檔案（例如另一個 session 正在補上游 PR），不限定路徑會把他們的進行中改動一起打包進你的 patch。

> Windows 的 PowerShell 沒有 `export`，用 `$env:GIT_INDEX_FILE = "..."`；或直接用 Git Bash 跑上面這段。

### 兩道交叉驗證（必做）

產完 patch 不要相信它，驗它：

**A. 全部 patch 疊加後的樹，要與工作區的樹相同**

```bash
cd vendor/ppt-master

# 從乾淨 HEAD 依序套用全部 patch，算出樹 SHA
export GIT_INDEX_FILE=/tmp/shiftdeck-stack-index
rm -f "$GIT_INDEX_FILE"; git read-tree HEAD
for p in ../../overlay/patches/*.patch; do git apply --cached "$p"; done
STACK=$(git write-tree)

# 把工作區現況讀進另一個臨時索引，算出樹 SHA
export GIT_INDEX_FILE=/tmp/shiftdeck-work-index
rm -f "$GIT_INDEX_FILE"; git read-tree HEAD
git add -A -- skills/
WORK=$(git write-tree)
unset GIT_INDEX_FILE

[ "$STACK" = "$WORK" ] && echo "相同" || git diff-tree -r --name-only "$STACK" "$WORK"
```

不同的話，最後一行會列出是哪些檔案沒被 patch 記錄到。**只有在工作區乾淨（除了 patch 內容之外沒有其他進行中改動）時才會相同**——多人同時動 `vendor/` 的話，先確認列出來的檔案不是你的。

**B. 乾淨 worktree 依序套用後，逐 byte 比對**

開一個乾淨的 worktree，`git apply` 每個 patch，然後跟你的工作區逐檔 `diff`。全部相同才算過。

這兩道在階段 3、4 都實際跑過，也真的抓到過東西——patch 產完就丟給下一個人，是最容易出事的地方。

---

## 不用寫程式就能加的東西

這兩類刻意設計成「加資料就好」，歡迎直接 PR：

**新增頁型**：一個資料夾（`skeleton.svg` 骨架兼縮圖 ＋ `contract.md` 重畫規則）＋ `overlay/pagetypes/catalog.json` 一筆。`id` 必須等於資料夾名。四語標籤與彈性範圍寫在 catalog 裡。

**新增動畫套組**：`overlay/animations/user/<id>.json`，格式沿用 `presets.json` 的 preset schema（`id` / `label_*` / `desc_*` / `defaults` / `page_roles` / `elements`）。也可以在編輯器裡改到滿意後用「套組另存」產生。

寫 `contract.md` 時務必遵守**跨軟體字型度量餘裕**規則——LibreOffice 對 CJK＋拉丁混排的字寬估算比 PowerPoint 寬 7–10%，會強制重斷行。這是真實踩過的坑。

---

## 送出前的檢查清單

**1. 兩道品質閘門，缺一不可**

```bash
# 幾何檢查（引擎內建）
python vendor/ppt-master/skills/ppt-master/scripts/svg_quality_checker.py projects/<專案> --stage final

# 真實渲染檢查
python scripts/visual_check.py projects/<專案>/exports/<檔名>.pptx
```

第二道產出的 PNG **要真的一頁一頁看過**。第一道回報 0 errors 但人眼一看就撐框，是這道閘門存在的原因。

**2. 新增的 UI 字串一律四語言**

`en` / `ja` / `zh` / `zh-TW`，一個都不能少。然後：

```bash
python scripts/check_zhtw.py
```

18 項全過才算數。它會檢查 zh-TW 覆蓋每一個 zh 鍵、沒有簡體殘留、語言選單有「繁體中文」。

**3. 零回歸**

新功能沒被啟用時，行為必須與改動前**完全一致**。可驗證的做法：從 `HEAD` 取出舊版腳本實跑，比對輸出逐鍵／逐 byte 相同。

**4. 動到 patch 就要更新 `engine.lock`**

`patched_files` 清單與 `patches` 說明都要同步。說明要寫「為什麼覆蓋層做不到」，不是寫「改了什麼」。

**5. 有實跑數字就給數字**

「應該會比較快」不算驗證。階段 4 的 26%、20 頁 3.007s vs 0.768s，都是實測值。反直覺的結果（例如單頁路徑的機械部分反而慢 0.94 秒）**照實寫**——那是誠實的邊界，不是瑕疵。

---

## Windows 開發注意

- `.ps1` 檔案要存成 **UTF-8 with BOM**，否則中文會變亂碼
- 引擎文件寫 `python3` 的地方，Windows 上用 `python`
- 路徑用絕對路徑；引擎的執行紀律明文要求不從 CWD 推導路徑

## Commit 與 PR

- Commit 訊息用中文，一行講清楚做了什麼（例：`階段 3：動畫選擇器（三套組 + 元素微調 + 即時預覽）`）
- PR 描述請包含：改了什麼、為什麼放在這一層、跑過哪些驗證（附實際數字）
- 影響 patch 的 PR，請附上你跑過交叉驗證的結果

## 回報問題

用 [Issue 範本](.github/ISSUE_TEMPLATE/)。錯誤回報請附上 `python scripts/setup.py --check` 的輸出——版本對不上是最常見的原因。
