import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "return_1w", "return_4w", "return_13w", "volatility_4w",
    "volatility_13w", "volume_change_4w", "benchmark_return_1w",
    "relative_return_4w", "drawdown_13w",
]


def build_features(weekly: pd.DataFrame) -> pd.DataFrame:
    f = weekly.copy()
    f["return_1w"] = f.close.pct_change()
    f["return_4w"] = f.close.pct_change(4)
    f["return_13w"] = f.close.pct_change(13)
    f["volatility_4w"] = f.return_1w.rolling(4).std()
    f["volatility_13w"] = f.return_1w.rolling(13).std()
    f["volume_change_4w"] = f.volume.pct_change(4)
    f["benchmark_return_1w"] = f.benchmark_close.pct_change()
    f["relative_return_4w"] = f.return_4w - f.benchmark_close.pct_change(4)
    f["drawdown_13w"] = f.close / f.close.rolling(13).max() - 1
    f["forward_return_1w"] = f.close.shift(-1) / f.close - 1
    return f.replace([np.inf, -np.inf], np.nan)
