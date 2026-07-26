"""Walk-forward challenger evaluation with cost-aware hedge thresholds."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import average_precision_score, recall_score


MIN_TRAIN_WEEKS = 260
RETRAIN_EVERY_WEEKS = 13
HEDGE_RATIO = 0.5
DEFAULT_HEDGE_COST = 0.003


def _max_drawdown(returns):
    wealth = (1.0 + pd.Series(returns).fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return abs(float(drawdown.min())) if len(drawdown) else 0.0


def _false_positive_rate(y_true, signals):
    y_true = np.asarray(y_true)
    signals = np.asarray(signals)
    negatives = y_true == 0
    return float(((signals == 1) & negatives).sum() / max(negatives.sum(), 1))


def _hedged_returns(next_returns, signals, cost):
    returns = np.asarray(next_returns, dtype=float)
    alarms = np.asarray(signals, dtype=float)
    protection = HEDGE_RATIO * np.maximum(-returns, 0.0) * alarms
    return returns + protection - cost * alarms


def choose_cost_aware_threshold(probabilities, y_true, next_returns, cost):
    probabilities = np.asarray(probabilities)
    candidates = np.unique(np.quantile(probabilities, np.linspace(0.55, 0.95, 17)))
    baseline_drawdown = _max_drawdown(next_returns)
    best = None
    for threshold in candidates:
        signals = probabilities >= threshold
        hedged_drawdown = _max_drawdown(
            _hedged_returns(next_returns, signals, cost)
        )
        drawdown_improvement = baseline_drawdown - hedged_drawdown
        net_return_lift = float(
            np.prod(1 + _hedged_returns(next_returns, signals, cost))
            - np.prod(1 + np.asarray(next_returns))
        )
        # Prefer economically useful drawdown reduction, then return lift,
        # while avoiding unnecessary false alarms and turnover.
        score = (
            drawdown_improvement,
            net_return_lift,
            -_false_positive_rate(y_true, signals),
            -float(np.mean(signals)),
        )
        if best is None or score > best[0]:
            best = (score, float(threshold))
    return best[1]


def evaluate_walk_forward(frame, feature_columns, hedge_cost=DEFAULT_HEDGE_COST):
    data = frame.dropna(subset=["Target_Ret"]).copy()
    usable_features = [
        column for column in feature_columns
        if column in data and data[column].notna().sum() >= MIN_TRAIN_WEEKS
    ]
    if len(data) < MIN_TRAIN_WEEKS + 52 or not usable_features:
        return None

    X = data[usable_features].replace([np.inf, -np.inf], np.nan)
    X = X.ffill().fillna(0.0)
    downside = data["Target_Ret"].iloc[:MIN_TRAIN_WEEKS].quantile(0.10)
    y = (data["Target_Ret"] < downside).astype(int)

    probabilities = np.full(len(data), np.nan)
    model = None
    for position in range(MIN_TRAIN_WEEKS, len(data)):
        if model is None or (position - MIN_TRAIN_WEEKS) % RETRAIN_EVERY_WEEKS == 0:
            model = ExtraTreesClassifier(
                n_estimators=300,
                min_samples_leaf=5,
                max_features=0.75,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X.iloc[:position], y.iloc[:position])
        probabilities[position] = model.predict_proba(X.iloc[[position]])[0, 1]

    oos = data.iloc[MIN_TRAIN_WEEKS:].copy()
    oos["probability"] = probabilities[MIN_TRAIN_WEEKS:]
    oos["target"] = y.iloc[MIN_TRAIN_WEEKS:].to_numpy()
    calibration_weeks = min(104, max(52, len(oos) // 3))
    if len(oos) <= calibration_weeks + 26:
        return None

    calibration = oos.iloc[:calibration_weeks]
    evaluation = oos.iloc[calibration_weeks:]
    threshold = choose_cost_aware_threshold(
        calibration["probability"],
        calibration["target"],
        calibration["Target_Ret"],
        hedge_cost,
    )
    signals = evaluation["probability"] >= threshold
    raw_returns = evaluation["Target_Ret"].to_numpy()
    hedged_returns = _hedged_returns(raw_returns, signals, hedge_cost)
    raw_drawdown = _max_drawdown(raw_returns)
    hedge_drawdown = _max_drawdown(hedged_returns)

    return {
        "prAuc": float(
            average_precision_score(evaluation["target"], evaluation["probability"])
        ),
        "recall": float(recall_score(evaluation["target"], signals, zero_division=0)),
        "falsePositiveRate": _false_positive_rate(evaluation["target"], signals),
        "rawMaxDrawdown": raw_drawdown,
        "hedgedMaxDrawdown": hedge_drawdown,
        "maxDrawdownImprovement": raw_drawdown - hedge_drawdown,
        "threshold": threshold,
        "hedgeCost": hedge_cost,
        "alertRate": float(signals.mean()),
        "evaluationWeeks": int(len(evaluation)),
        "latestProbability": float(oos["probability"].iloc[-1]),
        "latestSignal": bool(oos["probability"].iloc[-1] >= threshold),
        "featureCount": len(usable_features),
    }


def promotion_decision(challenger_metrics, official_history_weeks):
    """Conservative gate: challenger stays in shadow mode until all pass."""
    if not challenger_metrics:
        return False, ["尚無足夠的 walk-forward 樣本"]
    reasons = []
    if official_history_weeks < 52:
        reasons.append("官方籌碼 point-in-time 歷史尚未累積滿 52 週")
    if challenger_metrics["prAuc"] < 0.20:
        reasons.append("PR-AUC 尚未達 0.20")
    if challenger_metrics["recall"] < 0.50:
        reasons.append("Recall 尚未達 50%")
    if challenger_metrics["falsePositiveRate"] > 0.35:
        reasons.append("誤報率高於 35%")
    if challenger_metrics["maxDrawdownImprovement"] <= 0.02:
        reasons.append("扣除成本後最大回撤改善未達 2 個百分點")
    return not reasons, reasons
