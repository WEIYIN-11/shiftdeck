# 自訂動畫套組

這個資料夾放你自己的動畫套組，一個套組一個 `.json`，檔名就是套組 id。
放進來的套組會自動出現在確認頁與預覽編輯器的套組清單裡，跟三個內建套組並列，
清單上標「（自訂）」。**內建 id 優先**——用同名 id 不會蓋掉內建套組，只會被忽略。

## 怎麼產生

不用手寫。先套一個內建套組、在預覽編輯器裡改到滿意，再存成自己的：

```bash
# 從專案目前的 animations.json 反推成套組
python overlay/animations/apply_preset.py <專案> --save-preset my-deck --label "醫療簡報用" --derived-from professional
```

或在預覽編輯器的動畫面板，套組那一列填 id 與顯示名稱，按「存成我的套組」。

反推的原理：`animations.json` 是具體的（這一頁、這個 `<g id>`），套組是抽象的
（這一「類」元素）。中間的橋是展開時用的同一組分類規則——每個 group id 先分類，
同一類第一個出現的效果列就成為那一類的規則。所以原封不動存回去會得到原本的套組。

## 格式

與 `presets.json` 裡的一筆完全相同：

| 欄位 | 說明 |
|---|---|
| `id` | 小寫英數與 `-` `_`，最多 40 字元（檔名安全） |
| `label_en` / `label_zh` / `label_zh_tw` / `label_ja` | 清單顯示名 |
| `desc_*` | 選填，說明句 |
| `defaults` | deck 層轉場與動畫預設 |
| `page_roles` | 依頁面角色（cover／section／closing…）覆寫 |
| `elements` | 依元素類別（title／kpi／card／chart…）的效果列 |

### 選用：同類元素輪替

一頁四張卡全部同一招會看起來很機械。`elements` 的每一類可以加兩個選用欄位：

```json
"kpi": {
  "effects": [{ "effect": "entrance_fade", "duration": 0.45 }],
  "rotate": ["entrance_fade", "entrance_wipe", "entrance_zoom"],
  "progressive": { "duration": [0.5, 0.3] }
}
```

- `rotate`：同一頁同類元素依序輪流用這幾個效果。可以寫效果 key（沿用 `effects`
  第一列、只換效果），也可以寫完整的效果列陣列。
- `progressive`：同類元素之間把某個數值欄位線性拉開。上例是第一張 0.5 秒、
  最後一張 0.3 秒，中間平均分。

兩個都是選用的。沒寫這兩個鍵時展開結果與以前完全相同——三個內建套組沒有用到它們。

## 要不要進版控？

**你自己決定**，這個資料夾沒有被寫進 `.gitignore`。套組是你寫的內容，不是產物：
想跟團隊共用就 commit，只是個人偏好就別 commit（或自己加一行 ignore）。
