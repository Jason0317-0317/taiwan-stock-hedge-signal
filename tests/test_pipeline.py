import numpy as np
import pandas as pd
import pytest

from tailrisk.config import Config
from tailrisk.data import download_market_data
from tailrisk.features import FEATURE_COLUMNS, build_features
from tailrisk.model import train_and_forecast


def test_features_and_forward_target():
    index = pd.date_range("2020-01-03", periods=30, freq="W-FRI")
    weekly = pd.DataFrame({"close": 100*np.cumprod(np.full(30, 1.01)),
                           "benchmark_close": 200*np.cumprod(np.full(30, 1.005)),
                           "volume": np.linspace(1000, 2000, 30)}, index=index)
    result = build_features(weekly)
    assert result.return_1w.dropna().iloc[-1] == pytest.approx(.01)
    assert pd.isna(result.forward_return_1w.iloc[-1])


def test_training_probability_is_bounded():
    rng, rows = np.random.default_rng(42), 420
    frame = pd.DataFrame(rng.normal(0, .02, (rows, len(FEATURE_COLUMNS))),
                         columns=FEATURE_COLUMNS, index=pd.date_range("2015-01-02", periods=rows, freq="W-FRI"))
    frame["forward_return_1w"] = rng.normal(.002, .035, rows)
    frame.loc[frame.index[-1], "forward_return_1w"] = np.nan
    result = train_and_forecast(frame, Config())
    assert 0 <= result.probability <= 1
    assert result.training_rows == rows - 1


def test_download_excludes_incomplete_future_week(monkeypatch):
    index = pd.date_range("2026-07-20", periods=8, freq="B")
    columns = pd.MultiIndex.from_product([["Adj Close", "Volume"], ["2330.TW", "^TWII"]])
    raw = pd.DataFrame(100.0, index=index, columns=columns)
    monkeypatch.setattr("tailrisk.data.yf.download", lambda *args, **kwargs: raw)
    config = Config(min_training_weeks=-51)
    weekly = download_market_data(config)
    assert weekly.index.max() <= index.max()
