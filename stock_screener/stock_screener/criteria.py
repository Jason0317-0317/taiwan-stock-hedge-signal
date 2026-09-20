# -*- coding: utf-8 -*-
"""
13 項個股分析條件的量化判斷函式
每個函式回傳 dict，包含 passed(bool) 與 detail(說明/數值)
"""

import numpy as np
import pandas as pd
from .config import CONFIG
from . import indicators as ind


def check_1_roic_wacc(roic: float, wacc: float, is_traditional_hw: bool = False) -> dict:
    """1. ROIC 須大於 WACC 達15%以上（傳產/硬體廠5~10%）"""
    if roic is None or wacc is None:
        return {"passed": None, "detail": "缺少 ROIC 或 WACC 資料"}

    spread = roic - wacc
    if is_traditional_hw:
        lower = CONFIG["roic_wacc_spread_traditional"]
        upper = CONFIG["roic_wacc_spread_traditional_high"]
        passed = spread >= lower
        detail = f"傳產/硬體廠：ROIC-WACC={spread:.2%}（門檻{lower:.0%}~{upper:.0%}）"
    else:
        threshold = CONFIG["roic_wacc_spread_general"]
        passed = spread >= threshold
        detail = f"ROIC-WACC={spread:.2%}（門檻>= {threshold:.0%}）"

    return {"passed": passed, "detail": detail, "spread": spread}


def check_2_fcf_yield(fcf_per_share: float, price: float) -> dict:
    """2. 持續正的自由現金流（每股自由現金流殖利率須大於5%）"""
    if fcf_per_share is None or price is None or price == 0:
        return {"passed": None, "detail": "缺少每股FCF或股價資料"}

    fcf_yield = fcf_per_share / price
    threshold = CONFIG["fcf_yield_min"]
    passed = fcf_per_share > 0 and fcf_yield >= threshold
    detail = f"FCF殖利率={fcf_yield:.2%}（門檻>= {threshold:.0%}），若未達標須檢視資本支出是否為大循環布局"
    return {"passed": passed, "detail": detail, "fcf_yield": fcf_yield}


def check_3_revenue_vs_inventory_growth(revenue_growth: float, inventory_growth: float) -> dict:
    """3. 營收成長率須大於存貨成長率5%以上"""
    if revenue_growth is None or inventory_growth is None:
        return {"passed": None, "detail": "缺少營收或存貨成長率資料"}

    spread = revenue_growth - inventory_growth
    threshold = CONFIG["revenue_vs_inventory_growth_spread"]
    passed = spread >= threshold
    detail = f"營收成長率-存貨成長率={spread:.2%}（門檻>= {threshold:.0%}）"
    return {"passed": passed, "detail": detail, "spread": spread}


def check_4_moat_proxy(rd_ratio_series) -> dict:
    """
    4. 護城河是否持續變厚（量化代理：研發費用占營收比是否持續上升）
    質化判斷仍建議搭配年報/法說會確認護城河具體來源（品牌/專利/網路效應/轉換成本等）
    """
    if rd_ratio_series is None or len(rd_ratio_series) < 2:
        return {"passed": None, "detail": "缺少研發費用占營收比序列資料，且護城河本質需質化確認（年報/法說會）"}

    s = pd.Series(rd_ratio_series)
    trending_up = bool(s.is_monotonic_increasing)
    detail = f"研發費用占營收比序列={list(s)}，是否持續上升={trending_up}（僅為量化代理指標，護城河本質仍需質化判斷）"
    return {"passed": trending_up, "detail": detail}


def check_5_success_model_replication(qualitative_note: str = None) -> dict:
    """
    5. 過去成功模式是否可持續複製（本質為質化判斷）
    此函式僅提供結構化紀錄欄位，需人工依年報/法說會內容填寫判斷依據
    """
    return {
        "passed": None,
        "detail": qualitative_note or "此項需人工依年報/法說會判斷成功模式（如展店模式、產品線複製、市場複製等）是否可延續",
    }


def check_6_growth_momentum_proxy(rd_ratio_series, new_product_note: str = None) -> dict:
    """
    6. 是否有持續之成長動能（新產品/新市場/新客戶）
    量化代理：研發費用占營收比是否持續上升；質化仍需年報/法說會佐證
    """
    if rd_ratio_series is None or len(rd_ratio_series) < 2:
        return {"passed": None, "detail": new_product_note or "缺少研發費用占營收比資料，成長動能仍需質化確認"}

    s = pd.Series(rd_ratio_series)
    trending_up = bool(s.is_monotonic_increasing)
    detail = f"研發費用占營收比是否持續上升={trending_up}；質化補充：{new_product_note or '無'}"
    return {"passed": trending_up, "detail": detail}


def check_7_ccc_improving(ccc_series) -> dict:
    """7. 現金週轉率(CCC)是否持續優化（下降/縮減趨勢）"""
    if ccc_series is None or len(ccc_series) < 2:
        return {"passed": None, "detail": "缺少CCC歷史序列資料"}

    s = pd.Series(ccc_series)
    improving = bool(s.is_monotonic_decreasing)
    detail = f"CCC序列={list(s)}，是否持續縮減={improving}"
    return {"passed": improving, "detail": detail}


def check_8_pe_band_position(df_with_pe: pd.DataFrame) -> dict:
    """8. 目前股價位於本益比河流之位置（上/中/下緣）"""
    if df_with_pe is None or "PE" not in df_with_pe.columns:
        return {"passed": None, "detail": "缺少PE河流資料"}

    position = ind.pe_band_position(df_with_pe["PE"].dropna())
    detail = f"目前PE位於本益比河流：{position}"
    # 此項不做強制通過與否判斷，回傳位置資訊供決策參考
    return {"passed": None, "detail": detail, "position": position}


def check_9_bollinger_position(df_with_bb: pd.DataFrame) -> dict:
    """9. 目前股價位於布林通道之位置（上/中/下軌）及是否破底翻"""
    if df_with_bb is None or "BB_upper" not in df_with_bb.columns:
        return {"passed": None, "detail": "缺少布林通道資料"}

    result = ind.bollinger_position(df_with_bb)
    detail = f"布林通道位置：{result['position']}，是否破底翻：{result['broke_and_reversed']}"
    return {"passed": None, "detail": detail, **result}


def check_10_weekly_kd_golden_cross(df_with_kd: pd.DataFrame) -> dict:
    """10. 週KD是否在20以下，K值由下突破D值(黃金交叉)，並持續往上趨勢"""
    if df_with_kd is None or "K" not in df_with_kd.columns:
        return {"passed": None, "detail": "缺少週KD資料"}

    result = ind.kd_golden_cross_from_oversold(df_with_kd)
    passed = result["golden_cross_in_oversold"] and result["k_trending_up"]
    detail = f"20以下黃金交叉={result['golden_cross_in_oversold']}，K值持續向上={result['k_trending_up']}"
    return {"passed": passed, "detail": detail, **result}


def check_11_weekly_macd_turning(df_with_macd: pd.DataFrame) -> dict:
    """11. 週MACD柱狀體翻正，且柱狀體持續加大"""
    if df_with_macd is None or "MACD_hist" not in df_with_macd.columns:
        return {"passed": None, "detail": "缺少週MACD資料"}

    result = ind.macd_hist_turning_positive_and_expanding(df_with_macd)
    passed = result["turned_positive"] or result["expanding"]
    detail = f"柱狀體翻正={result['turned_positive']}，柱狀體持續放大={result['expanding']}"
    return {"passed": passed, "detail": detail, **result}


def check_12_big_holder_accumulation(weekly_holder_shares_series) -> dict:
    """12. 千張大戶是否連續4週增持"""
    if weekly_holder_shares_series is None or len(weekly_holder_shares_series) < CONFIG["big_holder_consecutive_weeks"] + 1:
        return {"passed": None, "detail": "缺少千張大戶週資料，需串接集保結算所股權分散表"}

    s = pd.Series(weekly_holder_shares_series)
    recent = s.iloc[-(CONFIG["big_holder_consecutive_weeks"] + 1):]
    diffs = recent.diff().dropna()
    passed = bool((diffs > 0).all())
    detail = f"近{CONFIG['big_holder_consecutive_weeks']}週千張大戶持股變化={list(diffs)}，是否連續增持={passed}"
    return {"passed": passed, "detail": detail}


def check_13_trust_buy_ratio(trust_buy_shares: float, total_volume: float, cap_type: str = "default") -> dict:
    """
    13. 當日投信買超占成交量比重是否達標
    cap_type: 'large' 大型股(門檻1%) / 'mid' 中型股(門檻3%) / 'default' 其他(門檻5%)
    """
    if trust_buy_shares is None or total_volume is None or total_volume == 0:
        return {"passed": None, "detail": "缺少投信買超或成交量資料，需串接證交所三大法人買賣超OpenAPI"}

    ratio = trust_buy_shares / total_volume
    threshold_map = {
        "large": CONFIG["trust_buy_ratio_large_cap"],
        "mid": CONFIG["trust_buy_ratio_mid_cap"],
        "default": CONFIG["trust_buy_ratio_default"],
    }
    threshold = threshold_map.get(cap_type, CONFIG["trust_buy_ratio_default"])
    passed = ratio >= threshold
    detail = f"投信買超占成交量比重={ratio:.2%}（{cap_type}股門檻>= {threshold:.0%}）"
    return {"passed": passed, "detail": detail, "ratio": ratio}
