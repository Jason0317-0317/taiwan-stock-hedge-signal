# 個股分析量化篩選系統

將個股分析的13項條件轉為可執行的量化程式碼，用於股票篩選/監控。

## 專案結構

```
stock_screener/
├── requirements.txt
├── README.md
└── stock_screener/
    ├── __init__.py
    ├── config.py       # 所有門檻參數集中設定
    ├── data_fetcher.py # 資料抓取（股價/基本面/籌碼面）
    ├── indicators.py   # 技術指標計算（KD、MACD、布林通道、PE河流）
    ├── criteria.py     # 13項條件的量化判斷邏輯
    └── main.py         # 主執行程式，整合所有條件並輸出報告
```

## 13項條件對應說明

| 編號 | 條件 | 量化程度 | 對應函式 |
|---|---|---|---|
| 1 | ROIC > WACC (一般15%+ / 傳產硬體5~10%) | 可量化，需財報資料 | `criteria.check_1_roic_wacc` |
| 2 | 自由現金流殖利率 > 5% | 可量化，需FCF/股本資料 | `criteria.check_2_fcf_yield` |
| 3 | 營收成長率 > 存貨成長率 5%以上 | 可量化，需財報資料 | `criteria.check_3_revenue_vs_inventory_growth` |
| 4 | 護城河持續變厚 | 質化為主，提供研發費用占比代理指標 | `criteria.check_4_moat_proxy` |
| 5 | 成功模式可複製 | 質化，需人工填寫年報/法說會判讀 | `criteria.check_5_success_model_replication` |
| 6 | 持續成長動能 | 質化為主，提供研發費用占比代理指標 | `criteria.check_6_growth_momentum_proxy` |
| 7 | CCC持續優化 | 可量化，需財報資料 | `criteria.check_7_ccc_improving` |
| 8 | PE河流位置 | 可量化，需歷史EPS序列 | `indicators.pe_band_position` |
| 9 | 布林通道位置/破底翻 | 可量化，股價資料自動計算 | `criteria.check_9_bollinger_position` |
| 10 | 週KD 20以下黃金交叉且續揚 | 可量化，股價資料自動計算 | `criteria.check_10_weekly_kd_golden_cross` |
| 11 | 週MACD柱狀體翻正放大 | 可量化，股價資料自動計算 | `criteria.check_11_weekly_macd_turning` |
| 12 | 千張大戶連續4週增持 | 可量化，需串接集保結算所資料 | `data_fetcher.fetch_big_holder_data`（待實作） |
| 13 | 投信買超占成交量比重達標 | 可量化，需串接三大法人資料 | `data_fetcher.fetch_trust_buy_data`（待實作） |

**注意**：yfinance 對台股基本面與籌碼面資料覆蓋有限，第1、2、3、4、6、7、12、13項
需自行串接以下資料源之一才能完整運作：
- 台灣證券交易所 OpenAPI: https://openapi.twse.com.tw/
- 公開資訊觀測站 (MOPS): https://mops.twse.com.tw/
- 台灣集保結算所股權分散表
- 財報狗、Goodinfo、TEJ 等第三方資料庫

程式已預留清楚的函式介面（標記 `TODO`），只需替換 `data_fetcher.py` 內對應函式的實作即可。

## 安裝與使用

```bash
pip install -r requirements.txt
python -m stock_screener.main --ticker 2330.TW
```

輸出範例（JSON格式）：
```json
{
  "9_Bollinger_Position": {
    "passed": null,
    "detail": "布林通道位置：中軌附近，是否破底翻：false",
    "position": "中軌附近",
    "broke_and_reversed": false
  },
  "10_Weekly_KD_Golden_Cross": {
    "passed": true,
    "detail": "20以下黃金交叉=true，K值持續向上=true"
  }
}
```

## 給 Manus / 部署到 GitHub 的建議步驟

1. 將本資料夾整個上傳/複製到新的 GitHub repository
2. 在 repo 根目錄確認含有 `requirements.txt`、`README.md`、`stock_screener/` 資料夾
3. 建議新增 `.gitignore`（排除 `__pycache__/`, `.venv/` 等）
4. 若要排程執行（如每日/每週自動篩選），可搭配 GitHub Actions：
   - 新增 `.github/workflows/screen.yml`，排程呼叫 `python -m stock_screener.main --ticker XXXX.TW`
   - 將結果輸出寫入 repo 內的 CSV/JSON，或串接通知（Line Notify/Email/Slack）
5. 若要接上籌碼面資料（第12、13項），需在 repo 的 Secrets 中設定對應 API 金鑰，
   並完成 `data_fetcher.py` 中 `fetch_big_holder_data` 與 `fetch_trust_buy_data` 的實作

## 免責聲明

本程式僅為量化篩選工具，協助將既定選股邏輯自動化，不構成任何投資建議。
所有門檻參數（`config.py`）與資料來源請依個人研究判斷調整，並自行承擔投資風險。
