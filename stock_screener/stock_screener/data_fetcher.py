# -*- coding: utf-8 -*-
"""
資料抓取模組
- 股價/技術面資料：使用 yfinance（支援台股，代號格式如 2330.TW）
- 基本面資料（ROIC、WACC、FCF、營收、存貨、CCC、研發費用等）：
  yfinance 對台股基本面資料支援有限，建議實務上串接：
    - 財報狗 / Goodinfo / 公開資訊觀測站 (MOPS) API 或爬蟲
    - TEJ、Wisers 等付費財經資料庫
  本檔案提供標準化的資料結構與函式介面，方便替換資料來源。
- 籌碼面資料（千張大戶、投信買賣超）：
  建議串接台灣證券交易所 OpenAPI (https://openapi.twse.com.tw/) 或
  證券櫃買中心 OpenAPI，本檔案提供對應函式的介面骨架（TODO 標記處）。
"""

import pandas as pd
import yfinance as yf


def fetch_price_history(ticker: str, period="2y", interval="1wk") -> pd.DataFrame:
    """
    抓取股價歷史資料（預設週線，近2年），供技術指標（KD/MACD/布林）使用
    ticker: 例如 '2330.TW'
    interval: '1d' 日線 / '1wk' 週線
    """
    data = yf.Ticker(ticker).history(period=period, interval=interval)
    data = data.rename(columns={"Open": "Open", "High": "High", "Low": "Low", "Close": "Close"})
    return data[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fetch_fundamentals(ticker: str) -> dict:
    """
    抓取基本面資料骨架。
    yfinance 對台股基本面資料（ROIC/WACC/FCF/存貨等）覆蓋不完整，
    此函式先嘗試從 yfinance 取得可得欄位，其餘欄位回傳 None，
    需由使用者自行接入財報狗/MOPS/TEJ 等資料源填補。
    """
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    fundamentals = {
        "market_cap": info.get("marketCap"),
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "free_cashflow": info.get("freeCashflow"),
        "shares_outstanding": info.get("sharesOutstanding"),
        # 下列欄位 yfinance 通常無法取得台股數據，需另行串接資料源
        "roic": None,          # TODO: 串接財報資料計算 ROIC
        "wacc": None,          # TODO: 依資金結構與利率計算 WACC
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "inventory_growth_yoy": None,   # TODO: 需財報存貨資料
        "rd_expense_ratio_series": None,  # TODO: 近幾期研發費用/營收序列
        "ccc_series": None,     # TODO: 近幾期現金週轉天數序列 (DIO+DSO-DPO)
    }
    return fundamentals


def fetch_big_holder_data(ticker: str):
    """
    千張大戶持股資料（籌碼面）。
    TODO: 串接台灣集保結算所 (TDCC) 股權分散表，
    或 TWSE OpenAPI 對應端點，取得「持有1000張以上大股東」週資料，
    回傳近N週的大戶持股張數序列，供判斷是否連續增持。
    """
    raise NotImplementedError(
        "請串接台灣集保結算所股權分散表或相關資料源以取得千張大戶資料"
    )


def fetch_trust_buy_data(ticker: str):
    """
    投信買賣超資料（籌碼面）。
    TODO: 串接證交所三大法人買賣超資料
    (例如 https://openapi.twse.com.tw/ 對應端點)，
    取得當日投信買超張數與當日成交量，計算買超占成交量比重。
    """
    raise NotImplementedError(
        "請串接台灣證交所三大法人買賣超 OpenAPI 以取得投信買超資料"
    )
