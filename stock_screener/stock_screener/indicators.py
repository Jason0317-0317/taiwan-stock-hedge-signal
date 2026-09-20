# -*- coding: utf-8 -*-
"""
技術指標計算：KD、MACD、布林通道、本益比河流
輸入皆為 pandas.DataFrame，欄位需包含 High, Low, Close (以及 PE 河流需要 Close, EPS)
"""

import numpy as np
import pandas as pd
from .config import CONFIG


def calc_kd(df: pd.DataFrame, period=None, smooth_k=None, smooth_d=None) -> pd.DataFrame:
    """計算 KD 指標（Stochastic Oscillator）。df 需含 High, Low, Close 欄位。"""
    period = period or CONFIG["kd_period"]
    smooth_k = smooth_k or CONFIG["kd_smooth_k"]
    smooth_d = smooth_d or CONFIG["kd_smooth_d"]

    low_min = df["Low"].rolling(window=period).min()
    high_max = df["High"].rolling(window=period).max()

    rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)

    k = rsv.ewm(alpha=1 / smooth_k, adjust=False).mean()
    d = k.ewm(alpha=1 / smooth_d, adjust=False).mean()

    out = df.copy()
    out["K"] = k
    out["D"] = d
    return out


def calc_macd(df: pd.DataFrame, fast=None, slow=None, signal=None) -> pd.DataFrame:
    """計算 MACD 指標。df 需含 Close 欄位。"""
    fast = fast or CONFIG["macd_fast"]
    slow = slow or CONFIG["macd_slow"]
    signal = signal or CONFIG["macd_signal"]

    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    out = df.copy()
    out["MACD"] = macd_line
    out["MACD_signal"] = signal_line
    out["MACD_hist"] = histogram
    return out


def calc_bollinger(df: pd.DataFrame, window=None, num_std=None) -> pd.DataFrame:
    """計算布林通道。df 需含 Close 欄位。"""
    window = window or CONFIG["bollinger_window"]
    num_std = num_std or CONFIG["bollinger_num_std"]

    mid = df["Close"].rolling(window=window).mean()
    std = df["Close"].rolling(window=window).std()

    out = df.copy()
    out["BB_mid"] = mid
    out["BB_upper"] = mid + num_std * std
    out["BB_lower"] = mid - num_std * std
    return out


def calc_pe_band(df: pd.DataFrame, eps_col="EPS") -> pd.DataFrame:
    """
    計算本益比河流所需的 PE 值序列。
    df 需含 Close 與 EPS（可為 TTM EPS）欄位。
    本益比河流的上中下緣，建議用歷史 PE 的百分位數（如 20/50/80 分位）來界定。
    """
    out = df.copy()
    out["PE"] = out["Close"] / out[eps_col]
    return out


def pe_band_position(pe_series: pd.Series, lower_q=0.2, upper_q=0.8) -> str:
    """
    判斷目前 PE 落在歷史 PE 河流的位置：上緣 / 中緣 / 下緣
    """
    current_pe = pe_series.iloc[-1]
    lower = pe_series.quantile(lower_q)
    upper = pe_series.quantile(upper_q)

    if current_pe >= upper:
        return "上緣"
    elif current_pe <= lower:
        return "下緣"
    else:
        return "中緣"


def bollinger_position(df: pd.DataFrame) -> dict:
    """
    判斷目前股價在布林通道的位置，以及是否有「破底翻」（跌破下軌後收復）現象
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    if latest["Close"] >= latest["BB_upper"]:
        position = "上軌"
    elif latest["Close"] <= latest["BB_lower"]:
        position = "下軌"
    else:
        position = "中軌附近"

    # 破底翻：前一根收盤在下軌之下，最新一根收盤已回到下軌之上
    broke_and_reversed = bool(
        (prev["Close"] < prev["BB_lower"]) and (latest["Close"] > latest["BB_lower"])
    )

    return {"position": position, "broke_and_reversed": broke_and_reversed}


def kd_golden_cross_from_oversold(df: pd.DataFrame, oversold=None) -> dict:
    """
    判斷週KD是否在20以下出現黃金交叉（K由下往上穿越D），且交叉後K值持續向上
    """
    oversold = oversold or CONFIG["kd_oversold_threshold"]
    if len(df) < 3:
        return {"golden_cross_in_oversold": False, "k_trending_up": False}

    k = df["K"]
    d = df["D"]

    cross_up = bool((k.iloc[-2] <= d.iloc[-2]) and (k.iloc[-1] > d.iloc[-1]))
    in_oversold_zone = bool(k.iloc[-2] < oversold or d.iloc[-2] < oversold)
    k_trending_up = bool(k.iloc[-1] > k.iloc[-2] > k.iloc[-3])

    return {
        "golden_cross_in_oversold": cross_up and in_oversold_zone,
        "k_trending_up": k_trending_up,
    }


def macd_hist_turning_positive_and_expanding(df: pd.DataFrame) -> dict:
    """
    判斷週MACD柱狀體是否翻正，且翻正後持續放大
    """
    hist = df["MACD_hist"]
    if len(hist) < 3:
        return {"turned_positive": False, "expanding": False}

    turned_positive = bool(hist.iloc[-2] <= 0 and hist.iloc[-1] > 0)
    expanding = bool(hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3] and hist.iloc[-1] > 0)

    return {"turned_positive": turned_positive, "expanding": expanding}
