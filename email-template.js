const fs = require("node:fs");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function percent(value, showSign = false) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  const sign = showSign && number >= 0 ? "+" : "";
  return `${sign}${(number * 100).toFixed(1)}%`;
}

function badge(signal, longLabel = false) {
  const className = signal ? "hedge" : "hold";
  const label = signal ? (longLabel ? "建議對沖" : "對沖") : (longLabel ? "正常持有" : "持有");
  return `<span class="badge ${className}">${label}</span>`;
}

function renderSummaryRow(stock) {
  const probabilityColor = stock.signal ? "#c0392b" : "#27ae60";
  return `
    <tr>
      <td><b>${escapeHtml(stock.ticker)}</b><br><span class="muted">${escapeHtml(stock.name)}</span></td>
      <td style="color:${probabilityColor};font-weight:bold;">${percent(stock.riskProbability)}</td>
      <td>${percent(stock.probabilityThreshold)}</td>
      <td style="color:#c0392b;font-weight:bold;">${escapeHtml(stock.downsideThresholdText)}</td>
      <td>${badge(stock.signal, true)}</td>
    </tr>`;
}

function renderHistoryRow(item) {
  const probabilityStyle = item.signal ? "color:#c0392b;font-weight:bold;" : "color:#333;";
  const returnColor = Number(item.weeklyReturn) < 0 ? "#c0392b" : "#27ae60";
  return `
    <tr>
      <td>${escapeHtml(item.date)}</td>
      <td style="${probabilityStyle}">${percent(item.riskProbability)}</td>
      <td style="color:${returnColor};">${percent(item.weeklyReturn, true)}</td>
      <td>${badge(item.signal)}</td>
    </tr>`;
}

function renderStockSection(stock) {
  const probabilityColor = stock.signal ? "#c0392b" : "#27ae60";
  const returnColor = Number(stock.weeklyReturn) < 0 ? "#c0392b" : "#27ae60";
  const historyRows = stock.history.map(renderHistoryRow).join("");

  return `
    <div class="section" id="section-${escapeHtml(stock.ticker)}">
      <div class="section-title">${escapeHtml(stock.ticker)} ${escapeHtml(stock.name)} 詳細分析</div>
      <div class="period forecast"><b>本週預測：</b>${escapeHtml(stock.forecastWeekRange)}｜風險機率與建議行動</div>
      <div class="period observed"><b>上週已完成：</b>${escapeHtml(stock.observationWeekRange)}｜已實現報酬 ${percent(stock.weeklyReturn, true)}</div>
      <div class="metrics">
        <div class="metric"><div class="val" style="color:${probabilityColor};">${percent(stock.riskProbability)}</div><div class="lbl">風險機率</div></div>
        <div class="metric"><div class="val">${percent(stock.probabilityThreshold)}</div><div class="lbl">機率觸發門檻</div></div>
        <div class="metric"><div class="val" style="color:#c0392b;">${escapeHtml(stock.downsideThresholdText)}</div><div class="lbl">尾部跌幅門檻</div></div>
        <div class="metric"><div class="val">${Number(stock.metrics.classWeight).toFixed(2)}×</div><div class="lbl">自動類別權重</div></div>
        <div class="metric"><div class="val">${percent(stock.metrics.f1)}</div><div class="lbl">模型 F1</div></div>
      </div>
      <p class="note">尾部跌幅門檻代表此股票歷史訓練期間最差 10% 週報酬的分界；模型用它定義「跌幅超過多少」屬於需要警戒的尾部風險事件。</p>
      <table class="history-table">
        <tr><th>預測週次</th><th>風險機率</th><th>該週實際報酬</th><th>訊號</th></tr>
        ${historyRows}
      </table>
    </div>`;
}

function renderEmail(report) {
  const challenger = report.challengerMetrics || {};
  const governance = report.modelGovernance || {};
  const promotionReasons = governance.promotionReasons || [];
  const summaryRows = report.stocks.map(renderSummaryRow).join("");
  const stockSections = report.stocks.map(renderStockSection).join("");

  return `<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  * { box-sizing: border-box; }
  body { font-family: "Helvetica Neue", Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }
  .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .header { background: #1a1a2e; color: white; padding: 28px 32px; }
  .header h1 { margin: 0; font-size: 20px; letter-spacing: 2px; color: #e0e0ff; }
  .section { padding: 24px 32px; border-bottom: 1px solid #eee; }
  .section-title { font-size: 14px; color: #333; font-weight: bold; letter-spacing: 1px; margin-bottom: 18px; border-left: 4px solid #1a1a2e; padding-left: 10px; }
  .metrics { display: flex; gap: 12px; margin-bottom: 15px; }
  .metric { flex: 1; background: #f9f9f9; border-radius: 6px; padding: 12px; text-align: center; border: 1px solid #eee; }
  .metric .val { font-size: 18px; font-weight: bold; }
  .metric .lbl { font-size: 11px; color: #999; margin-top: 4px; }
  .history-table, .summary-table { width: 100%; border-collapse: collapse; }
  .history-table { margin-top: 10px; }
  .history-table th { font-size: 11px; color: #999; text-align: left; padding: 8px 0; border-bottom: 1px solid #eee; }
  .history-table td { font-size: 12px; color: #333; padding: 8px 0; border-bottom: 1px solid #f5f5f5; }
  .summary-table { margin-bottom: 20px; }
  .summary-table th { background: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-size: 12px; }
  .summary-table td { padding: 12px; border-bottom: 1px solid #dee2e6; font-size: 12px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }
  .badge.hedge { background: #fff3cd; color: #856404; }
  .badge.hold { background: #d4edda; color: #155724; }
  .muted { color: #888; font-size: 11px; }
  .note { color: #777; font-size: 12px; line-height: 1.6; margin: 4px 0 12px; }
  .period { padding: 10px 12px; margin-bottom: 8px; border-radius: 6px; font-size: 12px; }
  .period.forecast { background: #eaf6fb; border: 1px solid #166c8c; }
  .period.observed { background: #f5f5f5; border: 1px solid #ddd; }
  .footer { padding: 16px 32px; background: #f9f9f9; font-size: 11px; color: #999; text-align: center; }
  @media (max-width: 600px) {
    body { padding: 0; }
    .header, .section { padding: 20px 16px; }
    .metrics { display: block; }
    .metric { margin-bottom: 8px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>多檔股票風險對沖通報</h1>
    <p>本週預測：${escapeHtml(report.forecastWeekRange)} | ${escapeHtml(report.model).toUpperCase()}</p>
  </div>
  <div class="section">
    <div class="section-title">本週預測與上週資料</div>
    <div class="period forecast"><b>本週｜尚未發生：</b>${escapeHtml(report.forecastWeekRange)}。風險機率與建議行動屬於模型預測。</div>
    <div class="period observed"><b>上週｜已完成資料：</b>${escapeHtml(report.observationWeekRange)}。週報酬與技術特徵來自這個交易週。</div>
  </div>
  <div class="section">
    <div class="section-title">模型歷史準確度</div>
    <div class="metrics">
      <div class="metric"><div class="val">${percent(report.modelMetrics.accuracy)}</div><div class="lbl">Accuracy</div></div>
      <div class="metric"><div class="val">${percent(report.modelMetrics.precision)}</div><div class="lbl">Precision</div></div>
      <div class="metric"><div class="val">${percent(report.modelMetrics.recall)}</div><div class="lbl">Recall</div></div>
      <div class="metric"><div class="val">${percent(report.modelMetrics.f1)}</div><div class="lbl">F1 Score</div></div>
    </div>
    <p class="note">類別權重已由訓練集內的時間序列驗證自動校準，平均為 ${Number(report.modelMetrics.averageClassWeight).toFixed(2)}×，調參驗證 F1 為 ${percent(report.modelMetrics.validationF1)}。最外層 ${escapeHtml(report.modelMetrics.testWeeks)} 個測試週完全不參與調參，含 ${escapeHtml(report.modelMetrics.tailEvents)} 次尾部事件。</p>
  </div>
  <div class="section">
    <div class="section-title">新模型影子評估｜${escapeHtml(governance.statusText || "資料累積中")}</div>
    <div class="metrics">
      <div class="metric"><div class="val">${percent(challenger.prAuc)}</div><div class="lbl">PR-AUC</div></div>
      <div class="metric"><div class="val">${percent(challenger.recall)}</div><div class="lbl">Recall</div></div>
      <div class="metric"><div class="val">${percent(challenger.falsePositiveRate)}</div><div class="lbl">誤報率</div></div>
      <div class="metric"><div class="val">${percent(challenger.maxDrawdownImprovement)}</div><div class="lbl">扣成本後回撤改善</div></div>
    </div>
    <p class="note">${escapeHtml(governance.thresholdPolicy || "依對沖成本調整門檻")}。官方 point-in-time 資料已累積 ${escapeHtml(governance.officialHistoryWeeks || 0)} 週。${promotionReasons.length ? `尚未替換：${escapeHtml(promotionReasons.join("、"))}` : "新模型已通過全部升級條件。"}</p>
  </div>
  <div class="section">
    <div class="section-title">全體股票摘要</div>
    <table class="summary-table">
      <tr><th>股票</th><th>風險機率</th><th>機率門檻</th><th>尾部跌幅門檻</th><th>建議行動</th></tr>
      ${summaryRows}
    </table>
    <p class="note">說明：是否建議對沖由 XGBoost 預測的風險機率判斷；「尾部跌幅門檻」則回答每支股票大約跌超過多少，會被模型標記為尾部風險事件。</p>
  </div>
  ${stockSections}
  <div class="footer">${escapeHtml(report.disclaimer)}</div>
</div>
</body>
</html>`;
}

const input = fs.readFileSync(0, "utf8");
const report = JSON.parse(input);
process.stdout.write(renderEmail(report));
