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
    hedge_recommended: bool
    hedge_threshold: float
    tail_threshold: float
    as_of: str
    training_rows: int
    positive_rows: int
    metrics: dict[str, float]
    hedge_stats: dict[str, float]
    recent_results: list[dict]


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
    realized = labelled.loc[valid, "forward_return_1w"].to_numpy()
    candidates = np.arange(.05, .951, .01)
    best = None
    for candidate in candidates:
        hedge = p >= candidate
        if hedge.sum() < config.min_hedge_weeks:
            continue
        if hedge.mean() > config.max_hedge_rate:
            continue
        protection = config.hedge_effectiveness * np.maximum(-realized, 0)
        net = hedge * (protection - config.weekly_hedge_cost)
        score = float(net.sum())
        if best is None or score > best[0]:
            best = (score, float(candidate), hedge, net)
    if best is None:
        best = (0.0, 1.0, np.zeros_like(p, dtype=bool), np.zeros_like(p))
    total_net, hedge_threshold, historical_hedge, hedge_net = best
    tail_events = y.to_numpy().astype(bool)
    hedge_stats = {
        "hedge_weeks": float(historical_hedge.sum()),
        "hedge_rate": float(historical_hedge.mean()),
        "tail_capture_rate": float((historical_hedge & tail_events).sum() / max(tail_events.sum(), 1)),
        "gross_loss_avoided": float(
            (historical_hedge * config.hedge_effectiveness * np.maximum(-realized, 0)).sum()
        ),
        "total_hedge_cost": float(historical_hedge.sum() * config.weekly_hedge_cost),
        "net_benefit": total_net,
        "average_net_per_hedge": float(hedge_net[historical_hedge].mean()) if historical_hedge.any() else 0.0,
    }
    recent_results = []
    recent_index = np.flatnonzero(valid.to_numpy())[-10:]
    for position in recent_index:
        probability_at_time = float(probabilities.iloc[position])
        actual_return = float(labelled["forward_return_1w"].iloc[position])
        actual_tail = bool(labels.iloc[position])
        recommended = bool(probability_at_time >= hedge_threshold and total_net > 0)
        net_result = (
            config.hedge_effectiveness * max(-actual_return, 0) - config.weekly_hedge_cost
            if recommended else 0.0
        )
        if recommended:
            outcome = "對沖有利" if net_result > 0 else "支付成本"
        else:
            outcome = "漏掉尾部" if actual_tail else "未對沖"
        recent_results.append({
            "as_of": labelled.index[position].date().isoformat(),
            "probability": probability_at_time,
            "hedge_recommended": recommended,
            "actual_return": actual_return,
            "actual_tail": actual_tail,
            "hedge_net_result": float(net_result),
            "outcome": outcome,
        })
    threshold = float(labelled.forward_return_1w.quantile(config.tail_quantile))
    final_y = (labelled.forward_return_1w <= threshold).astype(int)
    probability = float(make_model(config).fit(labelled[FEATURE_COLUMNS], final_y).predict_proba(latest[FEATURE_COLUMNS])[0, 1])
    return ForecastResult(
        probability=probability,
        signal=probability >= config.probability_threshold,
        hedge_recommended=probability >= hedge_threshold and total_net > 0,
        hedge_threshold=hedge_threshold,
        tail_threshold=threshold,
        as_of=latest.index[-1].date().isoformat(),
        training_rows=len(labelled),
        positive_rows=int(final_y.sum()),
        metrics=metrics,
        hedge_stats=hedge_stats,
        recent_results=recent_results,
    )
