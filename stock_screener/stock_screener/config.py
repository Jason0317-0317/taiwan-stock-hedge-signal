# -*- coding: utf-8 -*-
"""
全域設定與門檻參數
所有數字門檻集中在此檔案管理，方便日後依個人策略微調
"""

CONFIG = {
    # 1. ROIC vs WACC
    "roic_wacc_spread_general": 0.15,      # 一般產業：ROIC - WACC >= 15%
    "roic_wacc_spread_traditional": 0.05,  # 傳產/硬體廠下緣
    "roic_wacc_spread_traditional_high": 0.10,  # 傳產/硬體廠上緣

    # 2. 自由現金流殖利率
    "fcf_yield_min": 0.05,  # 每股自由現金流殖利率 > 5%

    # 3. 營收成長率 vs 存貨成長率
    "revenue_vs_inventory_growth_spread": 0.05,  # 營收成長率 - 存貨成長率 > 5%

    # 4/6. 護城河與成長動能量化代理指標（研發費用占營收比）
    "rd_ratio_lookback_periods": 4,  # 觀察近幾期（季/年）研發費用占營收比是否上升

    # 7. 現金週轉率 CCC
    "ccc_lookback_periods": 4,  # 觀察近幾期 CCC 是否持續下降(優化)

    # 9. 布林通道
    "bollinger_window": 20,
    "bollinger_num_std": 2,

    # 10. 週KD
    "kd_period": 9,
    "kd_smooth_k": 3,
    "kd_smooth_d": 3,
    "kd_oversold_threshold": 20,

    # 11. 週MACD
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,

    # 12. 千張大戶連續增持週數
    "big_holder_consecutive_weeks": 4,

    # 13. 投信買超占成交量比重門檻
    "trust_buy_ratio_mid_cap": 0.03,   # 中型股 3%以上
    "trust_buy_ratio_large_cap": 0.01,  # 大型股 1%以上
    "trust_buy_ratio_default": 0.05,   # 未分類時預設 5%以上

    # 市值分類門檻（新台幣，僅為預設示意值，請依實際產業/市場調整）
    "market_cap_large_cap_twd": 100_000_000_000,  # 1000億以上視為大型股
    "market_cap_mid_cap_twd": 10_000_000_000,     # 100億~1000億視為中型股
}
