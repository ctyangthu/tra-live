# 台鐵環島動態系統

線上版：<https://ctyangthu.github.io/tra-live/>

依臺鐵每日公告的時刻表，在台灣地圖上推算 EMU3000 新自強號（自強(3000)）沿環島鐵路的每一班列車位置。

## 功能

- **依日期套用班表**：使用臺鐵開放資料的每日時刻表，約涵蓋未來 60 天，每天約 70–80 班 EMU3000。超出公告範圍的日期，暫以最近一個同星期的日期推算。
- **即時與模擬**：預設使用台灣現在時間；可切換日期、拖曳時間軸，並以 1×–900× 播放。跨午夜仍在行駛的前一天列車會繼續顯示。
- **環島地圖**：縱貫線、山線、海線、屏東線、南迴線、臺東線、北迴線、宜蘭線，支線以虛線表示。列車沿各自的實際路徑移動並靠左行駛，順行（順時針）藍色、逆行（逆時針）橘色，虛框表示停靠中。點選列車會在地圖上標出全程路線。
- **列車詳情**：停靠站與到開時間、通過站數、下一站、估算時速、騰雲座艙／自由座車廂、60 天行駛日曆與臺鐵備註。
- **車站看板**：各站順行／逆行接下來的 EMU3000 班次。
- **起訖查詢**：任選兩站列出直達班次、行車時間與最快車次。
- **時刻表**：依方向、路線（西部幹線、東部幹線、經南迴線、西部↔東部）與車次篩選。

## 限制

- 列車位置依時刻表推算：車站之間以直線相連，加減速為估算，不含誤點等即時資訊。
- 只顯示 EMU3000（臺鐵車種代碼 110G、110H、110K，在臺鐵時刻查詢網頁上標示為「自強(3000)」）。
- 本系統為非官方展示，實際行車以臺鐵公告為準。

## 專案結構

```
src/app.html                  網頁原始碼（資料以佔位字串嵌入）
data/stations.json            臺鐵車站基本資料（代碼、站名、GPS）
data/emu3000.json             由每日時刻表整理出的 EMU3000 班表、車站與軌道圖
data/counties-10t.json        縣市界 TopoJSON（taiwan-atlas）
data/map.json                 投影並簡化後的地圖路徑
tools/fetch_timetable.py      下載臺鐵目前公告的所有每日時刻表 JSON
tools/extract_emu3000.py      整理出 EMU3000 班表，並從所有列車的停站順序推出軌道相鄰關係
tools/build_map.py            產生 data/map.json
tools/build.py                組出 dist/index.html
```

## 建置

```bash
python3 tools/build.py
```

產出的 `dist/index.html` 可直接用瀏覽器開啟。推送到 `main` 後，GitHub Actions 會自動建置並部署到 GitHub Pages。

## 更新時刻表

臺鐵每天更新開放資料，約提供未來 60 天的每日時刻表。GitHub Actions 每天 04:30（台灣時間）重新下載並部署，所以線上版會自動往後延伸；下載失敗時改用 repo 裡的 `data/emu3000.json`。

在本機更新時，原始檔約 120 MB，放在 `raw/`，不納入版本控制：

```bash
python3 tools/fetch_timetable.py raw
python3 tools/extract_emu3000.py raw data/emu3000.json
python3 tools/build.py
```

## 資料來源

- 時刻表：[臺鐵開放資料〈鐵路時刻表 JSON〉](https://ods.railway.gov.tw/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list)
- 車站：臺鐵開放資料〈車站基本資料集〉
- 車種對照：[臺鐵時刻查詢](https://www.railway.gov.tw/tra-tip-web/tip)
- 地圖：[taiwan-atlas](https://github.com/dkaoster/taiwan-atlas)（原始資料為內政部國土測繪中心開放資料）
