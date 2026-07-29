import json
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .model import ForecastResult


def render_report(r: ForecastResult, c: Config) -> str:
    status = "高風險警示" if r.signal else "未觸發警示"
    m = r.metrics
    return f"""# 台積電下一週尾部風險預測

- 資料截止日：{r.as_of}
- 狀態：**{status}**
- 尾部事件機率：**{r.probability:.1%}**
- 警示門檻：{c.probability_threshold:.0%}
- 左尾報酬門檻：{r.tail_threshold:.2%}
- 訓練樣本／尾部樣本：{r.training_rows}／{r.positive_rows}

| Walk-forward 指標 | 數值 |
|---|---:|
| PR-AUC | {m['pr_auc']:.3f} |
| ROC-AUC | {m['roc_auc']:.3f} |
| Precision | {m['precision']:.3f} |
| Recall | {m['recall']:.3f} |
| F2 | {m['f2']:.3f} |
| Brier score | {m['brier']:.3f} |
| 尾部事件基準率 | {m['base_rate']:.1%} |

僅供研究與教育用途，不構成投資建議。
"""


def write_outputs(r, c, output_dir=Path("artifacts")):
    output_dir.mkdir(parents=True, exist_ok=True)
    report = render_report(r, c)
    (output_dir / "latest_report.md").write_text(report, encoding="utf-8")
    (output_dir / "latest_prediction.json").write_text(
        json.dumps({"ticker": c.ticker, **asdict(r)}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
