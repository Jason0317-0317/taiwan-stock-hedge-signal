"""Point-in-time market features and official Taiwan market snapshots.

The official APIs mostly expose recent/current observations.  We therefore
append one dated snapshot on every weekly run and never backfill an old date
with a newer value.  This makes the cache safe for walk-forward evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import yfinance as yf


CACHE_PATH = Path("data/official_market_snapshots.csv")
GLOBAL_SYMBOLS = {
    "VIX": "^VIX",
    "USD_TWD": "TWD=X",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "SOX": "^SOX",
    "NIKKEI": "^N225",
}


def _get_json(url):
    request = Request(url, headers={"User-Agent": "tail-risk-research/1.0"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _number(value):
    if value is None:
        return np.nan
    text = str(value).replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return np.nan


def _latest_taifex_row(endpoint):
    rows = _get_json(f"https://openapi.taifex.com.tw/v1/{endpoint}")
    return rows[0] if rows else {}


def fetch_official_snapshot(as_of_date):
    """Fetch only information observable on the run date."""
    snapshot = {"date": pd.Timestamp(as_of_date).strftime("%Y-%m-%d")}

    try:
        row = _latest_taifex_row("PutCallRatio")
        snapshot["put_call_oi_ratio"] = _number(
            row.get("PutCallRatioByOpenInterest")
            or row.get("PutCallRatioByOI")
            or row.get("PutCallRatio")
            or row.get("PutCallOIRatio%")
        )
    except Exception as exc:
        print(f"Put/Call Ratio 暫時無法取得：{exc}")

    try:
        rows = _get_json(
            "https://openapi.taifex.com.tw/v1/"
            "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
        )
        foreign = next(
            (
                row
                for row in rows
                if "外資" in str(row.get("Item", ""))
                and row.get("ContractCode") == "臺股期貨"
            ),
            {},
        )
        long_oi = _number(
            foreign.get("OpenInterestOfLongPositions")
            or foreign.get("LongOpenInterest")
            or foreign.get("OpenInterest(Long)")
        )
        short_oi = _number(
            foreign.get("OpenInterestOfShortPositions")
            or foreign.get("ShortOpenInterest")
            or foreign.get("OpenInterest(Short)")
        )
        snapshot["foreign_futures_net"] = long_oi - short_oi
    except Exception as exc:
        print(f"外資期貨淨部位暫時無法取得：{exc}")

    date_text = pd.Timestamp(as_of_date).strftime("%Y%m%d")
    try:
        payload = _get_json(
            f"https://www.twse.com.tw/rwd/zh/fund/BFI82U"
            f"?date={date_text}&response=json"
        )
        fields = payload.get("fields", [])
        rows = [dict(zip(fields, row)) for row in payload.get("data", [])]
        foreign_rows = [row for row in rows if "外資" in str(row.get("單位名稱", ""))]
        snapshot["foreign_institutional_net"] = sum(
            _number(row.get("買賣差額")) for row in foreign_rows
        )
        snapshot["institutional_net"] = sum(
            _number(row.get("買賣差額")) for row in rows
        )
    except Exception as exc:
        print(f"法人流向暫時無法取得：{exc}")

    try:
        payload = _get_json(
            f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
            f"?date={date_text}&selectType=MS&response=json"
        )
        table = payload.get("tables", [{}])[0]
        fields = table.get("fields", [])
        rows = [dict(zip(fields, row)) for row in table.get("data", [])]
        for row in rows:
            item = str(row.get("項目", ""))
            if "融資" in item and "金額" in item:
                snapshot["margin_balance"] = _number(row.get("今日餘額"))
            elif "融券" in item and ("張數" in item or "交易單位" in item):
                snapshot["short_balance"] = _number(row.get("今日餘額"))
    except Exception as exc:
        print(f"融資融券暫時無法取得：{exc}")

    return snapshot


def update_official_cache(as_of_date):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_PATH.exists():
        cache = pd.read_csv(CACHE_PATH)
    else:
        cache = pd.DataFrame()

    snapshot = pd.DataFrame([fetch_official_snapshot(as_of_date)])
    cache = pd.concat([cache, snapshot], ignore_index=True)
    cache = cache.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    cache.to_csv(CACHE_PATH, index=False)
    return cache


def download_global_features(start):
    frames = []
    for label, symbol in GLOBAL_SYMBOLS.items():
        try:
            data = yf.download(symbol, start=start, auto_adjust=True, progress=False)
            if data.empty:
                continue
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [column[0] for column in data.columns]
            close = data["Close"].resample("W-FRI").last()
            frame = pd.DataFrame(index=close.index)
            frame[f"{label}_ret_1w"] = close.pct_change()
            frame[f"{label}_ret_4w"] = close.pct_change(4)
            frame[f"{label}_vol_4w"] = close.pct_change().rolling(4).std()
            if label in {"VIX", "USD_TWD"}:
                frame[f"{label}_level"] = close
            frames.append(frame)
        except Exception as exc:
            print(f"{label} 歷史資料暫時無法取得：{exc}")

    return pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()


def official_weekly_features(cache):
    if cache.empty:
        return pd.DataFrame()
    result = cache.copy()
    result["date"] = pd.to_datetime(result["date"])
    result = result.set_index("date").sort_index().resample("W-FRI").last()
    value_columns = list(result.columns)
    for column in value_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
        result[f"{column}_missing"] = result[column].isna().astype(float)
        result[f"{column}_change_1w"] = result[column].pct_change()
    # Only forward-fill: values never travel backward in time.
    result[value_columns] = result[value_columns].ffill(limit=4)
    return result
