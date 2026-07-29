from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from .config import Config


def download_market_data(config: Config) -> pd.DataFrame:
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=365 * config.years + 30)
    raw = yf.download(
        [config.ticker, config.benchmark], start=start.isoformat(), end=end.isoformat(),
        auto_adjust=False, progress=False, threads=True,
    )
    if raw.empty:
        raise RuntimeError("No market data returned")
    field = "Adj Close" if "Adj Close" in raw.columns.get_level_values(0) else "Close"
    close = raw[field]
    daily = pd.DataFrame({
        "close": close[config.ticker],
        "benchmark_close": close[config.benchmark],
        "volume": raw["Volume"][config.ticker],
    }).dropna(subset=["close", "benchmark_close"])
    weekly = pd.DataFrame({
        "close": daily["close"].resample("W-FRI").last(),
        "benchmark_close": daily["benchmark_close"].resample("W-FRI").last(),
        "volume": daily["volume"].resample("W-FRI").sum(),
    }).dropna()
    # A mid-week run is labelled with the upcoming Friday by pandas. Exclude that
    # incomplete bin so the forecast never reports a future or partial week.
    weekly = weekly.loc[weekly.index <= daily.index.max().normalize()]
    if len(weekly) < config.min_training_weeks + 52:
        raise RuntimeError(f"Insufficient weekly history: {len(weekly)}")
    return weekly
