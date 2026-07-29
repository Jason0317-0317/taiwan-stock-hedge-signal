from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    ticker: str = "2330.TW"
    benchmark: str = "^TWII"
    years: int = 20
    tail_quantile: float = 0.05
    probability_threshold: float = 0.35
    weekly_hedge_cost: float = 0.005
    hedge_effectiveness: float = 0.70
    min_hedge_weeks: int = 10
    max_hedge_rate: float = 0.25
    min_training_weeks: int = 260
    random_state: int = 42
