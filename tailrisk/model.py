from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, fbeta_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import Config
from .features import FEATURE_COLUMNS


@dataclass
class ForecastResult:
    probability: float
    signal: bool
    tail_threshold: float
    as_of: str
    training_rows: int
    positive_rows: int
    metrics: dict[str, float]


def make_model(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(class_weight="balanced", C=.5, max_iter=2000, random_state=config.random_state)),
    ])


def train_and_forecast(frame: pd.DataFrame, config: Config) -> ForecastResult:
    latest = frame.dropna(subset=FEATURE_COLUMNS).iloc[[-1]]
    labelled = frame.dropna(subset=FEATURE_COLUMNS + ["forward_return_1w"]).copy()
    if len(labelled) < config.min_training_weeks:
        raise ValueError("Not enough labelled observations")
    probabilities = pd.Series(index=labelled.index, dtype=float)
    labels = pd.Series(index=labelled.index, dtype=float)
    for train_idx, test_idx in TimeSeriesSplit(n_splits=5).split(labelled):
        train, test = labelled.iloc[train_idx], labelled.iloc[test_idx]
        threshold = train.forward_return_1w.quantile(config.tail_quantile)
        y_train = (train.forward_return_1w <= threshold).astype(int)
        labels.iloc[test_idx] = (test.forward_return_1w <= threshold).astype(int)
        probabilities.iloc[test_idx] = make_model(config).fit(train[FEATURE_COLUMNS], y_train).predict_proba(test[FEATURE_COLUMNS])[:, 1]
    valid = probabilities.notna()
    y, p = labels[valid].astype(int), probabilities[valid].to_numpy()
    pred = (p >= config.probability_threshold).astype(int)
    metrics = {
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f2": float(fbeta_score(y, pred, beta=2, zero_division=0)),
        "brier": float(brier_score_loss(y, p)),
        "base_rate": float(y.mean()),
    }
    threshold = float(labelled.forward_return_1w.quantile(config.tail_quantile))
    final_y = (labelled.forward_return_1w <= threshold).astype(int)
    probability = float(make_model(config).fit(labelled[FEATURE_COLUMNS], final_y).predict_proba(latest[FEATURE_COLUMNS])[0, 1])
    return ForecastResult(probability, probability >= config.probability_threshold, threshold,
                          latest.index[-1].date().isoformat(), len(labelled), int(final_y.sum()), metrics)
