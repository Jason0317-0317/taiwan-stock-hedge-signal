# -*- coding: utf-8 -*-
"""
主執行程式：對單一股票代號執行全部13項條件檢核，輸出彙整報告
使用範例：
    python -m stock_screener.main --ticker 2330.TW
"""

import argparse
import json

from . import data_fetcher as fetcher
from . import indicators as ind
from . import criteria as crit


def run_screening(ticker: str, is_traditional_hw: bool = False, cap_type: str = "default") -> dict:
    results = {}

    # --- 抓取股價與技術面資料 ---
    price_df = fetcher.fetch_price_history(ticker, period="2y", interval="1wk")
    price_df = ind.calc_kd(price_df)
    price_df = ind.calc_macd(price_df)
    price_df = ind.calc_bollinger(price_df)

    # --- 抓取基本面資料（部分欄位可能為 None，需自行補資料源）---
    fundamentals = fetcher.fetch_fundamentals(ticker)

    # 1. ROIC vs WACC
    results["1_ROIC_WACC"] = crit.check_1_roic_wacc(
        fundamentals.get("roic"), fundamentals.get("wacc"), is_traditional_hw
    )

    # 2. FCF殖利率
    latest_price = price_df["Close"].iloc[-1] if not price_df.empty else None
    shares = fundamentals.get("shares_outstanding")
    fcf = fundamentals.get("free_cashflow")
    fcf_per_share = (fcf / shares) if (fcf and shares) else None
    results["2_FCF_Yield"] = crit.check_2_fcf_yield(fcf_per_share, latest_price)

    # 3. 營收成長率 vs 存貨成長率
    results["3_Revenue_vs_Inventory_Growth"] = crit.check_3_revenue_vs_inventory_growth(
        fundamentals.get("revenue_growth_yoy"), fundamentals.get("inventory_growth_yoy")
    )

    # 4. 護城河（量化代理）
    results["4_Moat_Proxy"] = crit.check_4_moat_proxy(fundamentals.get("rd_expense_ratio_series"))

    # 5. 成功模式複製（質化，需人工填寫）
    results["5_Success_Model_Replication"] = crit.check_5_success_model_replication()

    # 6. 成長動能（量化代理）
    results["6_Growth_Momentum_Proxy"] = crit.check_6_growth_momentum_proxy(
        fundamentals.get("rd_expense_ratio_series")
    )

    # 7. CCC優化
    results["7_CCC_Improving"] = crit.check_7_ccc_improving(fundamentals.get("ccc_series"))

    # 8. PE河流位置（若有EPS資料才可計算，此處先跳過，需自行提供EPS序列）
    results["8_PE_Band_Position"] = {"passed": None, "detail": "需提供歷史EPS序列以計算PE河流，請參考 indicators.calc_pe_band"}

    # 9. 布林通道位置
    results["9_Bollinger_Position"] = crit.check_9_bollinger_position(price_df)

    # 10. 週KD黃金交叉
    results["10_Weekly_KD_Golden_Cross"] = crit.check_10_weekly_kd_golden_cross(price_df)

    # 11. 週MACD翻正
    results["11_Weekly_MACD_Turning"] = crit.check_11_weekly_macd_turning(price_df)

    # 12. 千張大戶連續增持（需另外串接集保資料）
    results["12_Big_Holder_Accumulation"] = {
        "passed": None,
        "detail": "需串接台灣集保結算所股權分散表，請參考 data_fetcher.fetch_big_holder_data",
    }

    # 13. 投信買超比重（需另外串接三大法人資料）
    results["13_Trust_Buy_Ratio"] = {
        "passed": None,
        "detail": "需串接證交所三大法人買賣超OpenAPI，請參考 data_fetcher.fetch_trust_buy_data",
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="個股13項條件量化篩選")
    parser.add_argument("--ticker", required=True, help="股票代號，例如 2330.TW")
    parser.add_argument("--traditional-hw", action="store_true", help="是否為傳產/硬體廠")
    parser.add_argument("--cap-type", default="default", choices=["large", "mid", "default"], help="市值分類")
    args = parser.parse_args()

    results = run_screening(args.ticker, args.traditional_hw, args.cap_type)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
