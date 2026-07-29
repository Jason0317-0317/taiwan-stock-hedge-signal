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


def render_email_html(r: ForecastResult, c: Config) -> str:
    status = "高風險警示" if r.signal else "未觸發警示"
    status_color = "#b42318" if r.signal else "#067647"
    status_bg = "#fef3f2" if r.signal else "#ecfdf3"
    m = r.metrics
    rows = [
        ("PR-AUC", m["pr_auc"], "越高越好"),
        ("ROC-AUC", m["roc_auc"], "越高越好"),
        ("Precision", m["precision"], "警示命中率"),
        ("Recall", m["recall"], "尾部事件捕捉率"),
        ("F2", m["f2"], "偏重 Recall"),
        ("Brier score", m["brier"], "越低越好"),
        ("尾部事件基準率", m["base_rate"], "樣本占比"),
    ]
    table_rows = "".join(
        f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eaecf0;color:#344054">{name}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eaecf0;text-align:right;font-weight:700;color:#101828">{value:.3f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eaecf0;color:#667085">{note}</td>
        </tr>"""
        for name, value, note in rows
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<body style="margin:0;background:#f2f4f7;font-family:Arial,'Noto Sans TC',sans-serif;color:#101828">
  <div style="display:none;max-height:0;overflow:hidden">台積電下一週尾部風險機率 {r.probability:.1%}</div>
  <div style="max-width:680px;margin:0 auto;padding:24px 12px">
    <div style="background:#ffffff;border:1px solid #eaecf0;border-radius:16px;overflow:hidden">
      <div style="padding:28px 28px 20px;background:#101828;color:#ffffff">
        <div style="font-size:13px;letter-spacing:1px;color:#98a2b3">TSMC · 2330.TW</div>
        <h1 style="margin:8px 0 4px;font-size:25px">下一週尾部風險預測</h1>
        <div style="font-size:14px;color:#d0d5dd">資料截止日：{r.as_of}</div>
      </div>
      <div style="padding:24px 28px">
        <div style="padding:18px;border-radius:12px;background:{status_bg};border-left:5px solid {status_color}">
          <div style="font-size:14px;color:{status_color};font-weight:700">{status}</div>
          <div style="margin-top:4px;font-size:38px;line-height:1.1;font-weight:800;color:{status_color}">{r.probability:.1%}</div>
          <div style="margin-top:6px;font-size:13px;color:#475467">模型估計的下一週左尾事件機率</div>
        </div>
        <table role="presentation" style="width:100%;margin:20px 0;border-collapse:separate;border-spacing:8px">
          <tr>
            <td style="width:50%;padding:14px;background:#f9fafb;border-radius:10px">
              <div style="font-size:12px;color:#667085">警示門檻</div>
              <div style="margin-top:4px;font-size:20px;font-weight:700">{c.probability_threshold:.0%}</div>
            </td>
            <td style="width:50%;padding:14px;background:#f9fafb;border-radius:10px">
              <div style="font-size:12px;color:#667085">左尾報酬門檻</div>
              <div style="margin-top:4px;font-size:20px;font-weight:700">{r.tail_threshold:.2%}</div>
            </td>
          </tr>
        </table>
        <h2 style="margin:26px 0 10px;font-size:18px">Walk-forward 模型評分</h2>
        <div style="font-size:13px;color:#667085;margin-bottom:12px">訓練樣本 {r.training_rows:,} 週 · 尾部樣本 {r.positive_rows:,} 週</div>
        <table style="width:100%;border-collapse:collapse;border:1px solid #eaecf0;border-radius:10px">
          <thead><tr style="background:#f9fafb">
            <th style="padding:10px 12px;text-align:left;color:#475467">指標</th>
            <th style="padding:10px 12px;text-align:right;color:#475467">分數</th>
            <th style="padding:10px 12px;text-align:left;color:#475467">說明</th>
          </tr></thead>
          <tbody>{table_rows}</tbody>
        </table>
        <p style="margin:22px 0 0;font-size:12px;line-height:1.6;color:#667085">
          本報告由統計模型自動產生，僅供研究與教育用途，不構成投資建議。
        </p>
      </div>
    </div>
  </div>
</body>
</html>"""


def write_outputs(r, c, output_dir=Path("artifacts")):
    output_dir.mkdir(parents=True, exist_ok=True)
    report = render_report(r, c)
    (output_dir / "latest_report.md").write_text(report, encoding="utf-8")
    (output_dir / "latest_prediction.json").write_text(
        json.dumps({"ticker": c.ticker, **asdict(r)}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
