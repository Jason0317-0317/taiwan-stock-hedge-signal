# XGBoost 台股尾部風險對沖分析

這是一個以 XGBoost 建立的台股尾部風險分析與對沖訊號專案。專案會下載台股與台灣加權指數資料，轉成週資料後建立技術特徵，訓練模型辨識下跌風險，並產生對沖訊號。

## 功能

- 下載個股與大盤歷史資料
- 以週頻率建立特徵，例如波動率、均線乖離、動能、成交量變化與近期低點距離
- 使用 XGBoost 分類模型預測尾部下跌風險
- Streamlit 互動介面顯示模型指標與回測績效
- 每週自動產生多檔股票風險訊號並寄出 email 報告

## 主要檔案

```text
XGBoost/
├── app.py                         # Streamlit 互動分析介面
├── hedge_signal.py                # 每週風險訊號與 email 報告腳本
├── requirements.txt               # Python 依賴
└── .github/workflows/weekly_signal.yml
```

## 分析股票

目前預設分析以下台股：

- 2330.TW 台積電
- 2454.TW 聯發科
- 2308.TW 台達電
- 2317.TW 鴻海
- 3711.TW 日月光
- 2383.TW 台光電
- 2327.TW 國巨
- 2303.TW 聯電
- 2881.TW 富邦金
- 1303.TW 南亞

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
