# XGBoost 台股尾部風險對沖分析

這是一個以 XGBoost 建立的台股尾部風險分析與對沖訊號專案。專案會下載台股與台灣加權指數資料，轉成週資料後建立技術特徵，訓練模型辨識下跌風險，並產生對沖訊號。

## 功能

- 下載個股與大盤歷史資料
- 以週頻率建立特徵，例如波動率、均線乖離、動能、成交量變化與近期低點距離
- 使用 XGBoost 分類模型預測尾部下跌風險
- Streamlit 互動介面顯示模型指標與回測績效
- 每週自動產生多檔股票風險訊號並寄出 email 報告
- Email 報告會顯示每支股票的「尾部跌幅門檻」，也就是該股票週報酬跌超過多少會被模型視為尾部風險事件

## 主要檔案

```text
taiwan-stock-hedge-signal/
├── app.py                         # Streamlit 互動分析介面
├── hedge_signal.py                # 每週風險訊號與 email 報告腳本
├── requirements.txt               # Python 依賴
└── .github/workflows/weekly_signal.yml
```

## Email 週報監控股票

`hedge_signal.py` 目前預設寄信監控以下台股：

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

## 安裝

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

## GitHub Actions 自動週報

`.github/workflows/weekly_signal.yml` 會在台灣時間每週日 08:00 執行，也可以手動觸發。

需要設定以下 GitHub Secrets：

- `SENDER_EMAIL`
- `SENDER_PASSWORD`
- `RECEIVER_EMAIL`

## 注意事項

- 模型結果僅供研究與風險控管參考，不構成投資建議。
- yfinance 資料可能受網路、資料源或 ticker 格式影響。
- 對沖成本、滑價與 carry rate 目前寫在程式常數中，可依實際交易條件調整。
