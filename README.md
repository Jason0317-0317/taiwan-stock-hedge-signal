# TSMC Tail-Risk Forecast

以過去 20 年週資料預測台積電（`2330.TW`）下一週是否進入左尾風險區。模型使用相對變動特徵、時間序列 walk-forward 驗證，以及 `class_weight="balanced"` 處理罕見事件。

> 本專案僅供研究與教育用途，不構成投資建議。

## 方法

- **標籤**：下一週報酬落在當時訓練資料中跌幅最大的 10%（第 10 百分位以下）。每個 walk-forward 分割都只用該折訓練期重新估計門檻。
- **特徵**：台積電與台灣加權指數的週報酬、動能、滾動波動率、成交量變化、相對強弱和回撤。
- **防止洩漏**：特徵只使用預測當下已知資料；驗證採 `TimeSeriesSplit`，每折的尾部門檻只由該折訓練期估計。
- **模型**：具標準化與類別權重的 Logistic Regression。
- **評估**：PR-AUC、ROC-AUC、precision、recall、F2、Brier score。
- **對沖決策**：在 walk-forward 預測上搜尋可產生最高歷史淨效益的觸發門檻；預設假設每週對沖成本 0.5%、抵銷 70% 當週下跌，且最多對沖歷史樣本的 25%。郵件會揭露門檻、尾部捕捉率、毛損失減少、成本與淨效益。
- **結果追蹤**：郵件列出最近 10 個已有實際結果的預測週，對照當時機率、回溯建議、下一週報酬、尾部事件與對沖淨結果。

20 年週資料約 1,000 筆，最差 10% 約有 100 個風險事件。專案採低複雜度、可解釋的基準模型，不把 accuracy 當主要指標。

## 本機執行

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
python -m tailrisk
pytest
```

產物會寫入 `artifacts/latest_prediction.json` 與 `artifacts/latest_report.md`。

## 每週自動化

GitHub Actions 於每週六台北時間 09:00 執行，也支援手動觸發。郵件正文包含當週預測與完整模型評分表。設定以下 Repository Secrets 後會透過 Gmail SMTP 寄出報告：

- `SENDER_EMAIL`
- `SENDER_PASSWORD`（Gmail App Password）
- `RECEIVER_EMAIL`

未設定郵件 Secrets 時，預測仍會執行並保存 workflow artifact。

## 結構

```text
tailrisk/        核心資料、特徵、模型、報告與郵件模組
tests/           無網路單元測試
.github/         每週自動化
artifacts/       執行產物（不提交）
```
