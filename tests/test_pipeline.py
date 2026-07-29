import numpy as np
import pandas as pd
import pytest

from tailrisk.config import Config
from tailrisk.data import download_market_data
from tailrisk.features import FEATURE_COLUMNS, build_features
from tailrisk.model import train_and_forecast
from tailrisk.reporting import render_email_html


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
    assert 38 <= result.positive_rows <= 46
    assert .05 <= result.hedge_threshold <= 1
    assert "net_benefit" in result.hedge_stats
    assert len(result.recent_results) == 10
    assert {"as_of", "week_start", "week_end", "probability", "hedge_recommended", "actual_return", "actual_tail", "outcome"} <= result.recent_results[-1].keys()
    assert (pd.Timestamp(result.recent_results[-1]["week_end"]) - pd.Timestamp(result.recent_results[-1]["week_start"])).days == 4


def test_download_excludes_incomplete_future_week(monkeypatch):
    index = pd.date_range("2026-07-20", periods=8, freq="B")
    columns = pd.MultiIndex.from_product([["Adj Close", "Volume"], ["2330.TW", "^TWII"]])
    raw = pd.DataFrame(100.0, index=index, columns=columns)
    monkeypatch.setattr("tailrisk.data.yf.download", lambda *args, **kwargs: raw)
    config = Config(min_training_weeks=-51)
    weekly = download_market_data(config)
    assert weekly.index.max() <= index.max()


def test_download_retries_incomplete_market_data(monkeypatch):
    index = pd.date_range("2026-07-01", periods=280, freq="B")
    incomplete = pd.DataFrame()
    columns = pd.MultiIndex.from_product([["Adj Close", "Volume"], ["2330.TW", "^TWII"]])
    complete = pd.DataFrame(100.0, index=index, columns=columns)
    responses = iter([incomplete, complete])
    calls = []

    def fake_download(*args, **kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr("tailrisk.data.yf.download", fake_download)
    monkeypatch.setattr("tailrisk.data.sleep", lambda _: None)
    weekly = download_market_data(Config(min_training_weeks=-1))
    assert not weekly.empty
    assert len(calls) == 2
    assert calls[0]["threads"] is False


def test_html_email_contains_scores():
    rng, rows = np.random.default_rng(7), 420
    frame = pd.DataFrame(rng.normal(0, .02, (rows, len(FEATURE_COLUMNS))),
                         columns=FEATURE_COLUMNS, index=pd.date_range("2015-01-02", periods=rows, freq="W-FRI"))
    frame["forward_return_1w"] = rng.normal(.002, .035, rows)
    frame.loc[frame.index[-1], "forward_return_1w"] = np.nan
    result = train_and_forecast(frame, Config())
    html = render_email_html(result, Config())
    assert "<html" in html
    assert "PR-AUC" in html
    assert "Brier score" in html
    assert "量化對沖決策" in html
    assert "回測淨效益" in html
    assert "最近 10 週建議與實際結果" in html
    assert result.recent_results[-1]["week_start"][5:] in html
    assert result.recent_results[-1]["week_end"][5:] in html
    assert f"{result.probability:.1%}" in html
