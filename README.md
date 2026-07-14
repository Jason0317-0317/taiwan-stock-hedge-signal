# XGBoost 台股尾部風險對沖分析

這是一個以 XGBoost 建立的台股尾部風險分析與對沖訊號專案。專案會下載台股與台灣加權指數資料，轉成週資料後建立技術特徵，訓練模型辨識下跌風險，並產生對沖訊號。

## 功能

- 下載個股與大盤歷史資料
- 以週頻率建立特徵，例如波動率、均線乖離、動能、成交量變化與近期低點距離
- 使用 XGBoost 分類模型預測尾部下跌風險
- Streamlit 互動介面顯示模型指標與回測績效
- Node.js 網站儀表板顯示每週風險訊號
- 網站儀表板提供風險機率排行、訊號分布、風險/報酬散點圖與近 6 週風險趨勢圖
- 每週自動產生多檔股票風險訊號並寄出 email 報告
- Email 報告與網站儀表板都會顯示每支股票的「尾部跌幅門檻」，也就是該股票週報酬跌超過多少會被模型視為尾部風險事件

## 主要檔案

```text
taiwan-stock-hedge-signal/
├── app.py                         # Streamlit 互動分析介面
├── hedge_signal.py                # 每週風險訊號、email 報告與網站資料輸出腳本
├── package.json                   # Node.js 網站依賴與啟動指令
├── server.js                      # Express 網站伺服器
├── vercel.json                    # Vercel 部署設定
├── public/
│   ├── index.html                 # 網站頁面與圖表區塊
│   ├── styles.css                 # 網站樣式與響應式圖表排版
│   ├── app.js                     # 網站資料渲染與 Chart.js 圖表邏輯
│   └── report-data.json           # 週報資料，由 hedge_signal.py 更新
├── requirements.txt               # Python 依賴
└── .github/workflows/weekly_signal.yml
```

## Email 週報監控股票

`hedge_signal.py` 目前預設寄信監控以下 10 檔台股：

- 2330.TW 台積電
- 2454.TW 聯發科
- 2317.TW 鴻海
- 3711.TW 日月光
- 2303.TW 聯電
- 2308.TW 台達電
- 2383.TW 台光電
- 2327.TW 國巨
- 1303.TW 南亞
- 2881.TW 富邦金

> 備註：國巨的 yfinance 台股代號使用 `2327.TW`。

## 報告欄位說明

- 風險機率：XGBoost 預測目前落入尾部下跌風險的機率。
- 機率門檻：模型將風險機率最高的前 10% 視為對沖訊號。
- 尾部跌幅門檻：訓練期間每檔股票「最差 10% 週報酬」的分界。例如顯示「跌超過 5.3%」，代表該股票單週跌幅超過約 5.3% 會被模型視為尾部風險事件。
- 建議行動：風險機率高於機率門檻時顯示「建議對沖」，否則為「正常持有」。

## 網站圖表說明

Node.js 儀表板會把 `public/report-data.json` 轉成以下圖表：

- 風險機率排行：比較每檔股票目前風險機率與模型觸發門檻。
- 訊號分布：統計目前有幾檔建議對沖、幾檔正常持有。
- 風險與報酬：用散點圖同時觀察上週報酬與風險機率，高風險且負報酬的股票優先檢查。
- 近 6 週風險趨勢：顯示目前風險較高股票的近期風險機率變化。

上方的「全部 / 建議對沖 / 正常持有」與搜尋框會同步影響圖表、卡片與摘要表。

## 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

## 執行 Streamlit 介面

```bash
streamlit run app.py
```

## 執行週報腳本

```bash
python hedge_signal.py
```

執行後會產生或更新：

- `public/report-data.json`：Node.js 網站使用的週報資料
- `report.html`：未設定寄信環境變數時產生的 email 預覽檔

## 執行 Node.js 網站

```bash
npm install
npm start
```

預設會在本機啟動：

```text
http://localhost:3000
```

網站會透過 `/api/report` 讀取 `public/report-data.json`，並顯示 10 檔股票的風險卡片、風險機率、尾部跌幅門檻、上週報酬、近期訊號與互動圖表。

## 部署到 Vercel

此專案已包含 `vercel.json`，可以直接把 GitHub repo 匯入 Vercel：

- Framework Preset：Other
- Build Command：留空或使用 Vercel 預設
- Output Directory：留空
- Install Command：`npm install`
- Start Command：`npm start`

每週 GitHub Actions 執行 `hedge_signal.py` 後，會更新並提交 `public/report-data.json`。如果 Vercel 已連接此 repo，新的資料提交會觸發網站重新部署。

## GitHub Actions 自動週報

`.github/workflows/weekly_signal.yml` 會在台灣時間每週日 08:00 執行，也可以手動觸發。流程會：

- 產生 10 檔股票風險訊號
- 寄出 Email 週報
- 更新 `public/report-data.json`
- 將最新網站資料提交回 repo

需要設定以下 GitHub Secrets：

- `SENDER_EMAIL`
- `SENDER_PASSWORD`
- `RECEIVER_EMAIL`

## 注意事項

- 模型結果僅供研究與風險控管參考，不構成投資建議。
- yfinance 資料可能受網路、資料源或 ticker 格式影響。
- 對沖成本、滑價與 carry rate 目前寫在程式常數中，可依實際交易條件調整。
