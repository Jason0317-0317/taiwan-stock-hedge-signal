import yfinance as yf
import pandas as pd
import numpy as np
import xgboost as xgb
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# =========================================================
# 1. 資料下載與清洗
# =========================================================
def get_cleaned_data(ticker, mkt_ticker, start):
    df_asset = yf.download(ticker, start=start, auto_adjust=True)
    df_mkt   = yf.download(mkt_ticker, start=start, auto_adjust=True)

    if df_asset.empty or df_mkt.empty:
        return pd.DataFrame()

    if isinstance(df_asset.columns, pd.MultiIndex):
        df_asset.columns = [col[0] for col in df_asset.columns]
    if isinstance(df_mkt.columns, pd.MultiIndex):
        df_mkt.columns = [col[0] for col in df_mkt.columns]

    df_w = pd.DataFrame({
        'Close':     df_asset['Close'].resample('W-FRI').last(),
        'Volume':    df_asset['Volume'].resample('W-FRI').sum(),
        'Mkt_Close': df_mkt['Close'].resample('W-FRI').last()
    }).dropna()

    return df_w

# =========================================================
# 2. 特徵工程
# =========================================================
def build_features(df):
    df = df.copy()
    df['Ret']        = df['Close'].pct_change()
    df['Mkt_Ret']    = df['Mkt_Close'].pct_change()
    df['Volat_4w']   = df['Ret'].rolling(4).std()
    df['Volat_12w']  = df['Ret'].rolling(12).std()
    df['Vol_Ratio']  = df['Volat_4w'] / (df['Volat_12w'] + 1e-6)
    df['MA_4']       = df['Close'].rolling(4).mean()
    df['MA_12']      = df['Close'].rolling(12).mean()
    df['Bias_4w']    = (df['Close'] - df['MA_4']) / (df['MA_4'] + 1e-6)
    df['MA_Spread']  = (df['MA_4'] - df['MA_12']) / (df['MA_12'] + 1e-6)
    df['Mom_4w']     = df['Close'].pct_change(4)
    df['Vol_Change'] = df['Volume'].pct_change()
    df['Ret_Lag1']   = df['Ret'].shift(1)
    df['Ret_Lag2']   = df['Ret'].shift(2)
    low_4w           = df['Close'].rolling(4).min()
    df['Dist_Low_4w']= (df['Close'] - low_4w) / (low_4w + 1e-6)

    # 處理 NaN 和 Inf
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()

    return df

# =========================================================
# 3. 核心處理邏輯
# =========================================================
def process_ticker(ticker, mkt_ticker, start_date):
    features = ['Volat_4w', 'Vol_Ratio', 'Bias_4w', 'MA_Spread',
                'Mom_4w', 'Vol_Change', 'Ret_Lag1', 'Ret_Lag2', 'Dist_Low_4w']
    
    df_raw  = get_cleaned_data(ticker, mkt_ticker, start_date)
    if df_raw.empty or len(df_raw) < 20:
        return None
    
    df_feat = build_features(df_raw)
    if len(df_feat) < 15:
        return None

    split_idx = int(len(df_feat) * 0.8)
    train_df  = df_feat.iloc[:split_idx]
    
    risk_threshold = train_df['Ret'].quantile(0.10)
    y_train = (train_df['Ret'] < risk_threshold).astype(int)
    X_train = train_df[features]
    
    # 防止 y_train 只有一類導致 XGBoost 報錯
    if len(np.unique(y_train)) < 2:
        return None

    pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.7,
        colsample_bytree=0.7,
        scale_pos_weight=pos_weight,
        eval_metric='logloss',
        random_state=42
    )
    model.fit(X_train, y_train)
    
    all_proba = model.predict_proba(df_feat[features])[:, 1]
    threshold = np.percentile(all_proba, 90)
    
    latest_prob = all_proba[-1]
    latest_date = df_feat.index[-1]
    latest_ret  = df_feat['Ret'].iloc[-1]
    signal      = latest_prob >= threshold
    
    history_df = df_feat.iloc[-6:].copy()
    history_proba = all_proba[-6:]
    
    return {
        'ticker': ticker,
        'latest_prob': latest_prob,
        'threshold': threshold,
        'latest_date': latest_date,
        'latest_ret': latest_ret,
        'signal': signal,
        'history_df': history_df,
        'history_proba': history_proba
    }

# =========================================================
# 4. 主程式
# =========================================================
TICKERS = ["2330.TW", "2454.TW", "2308.TW", "2317.TW", "3711.TW", "2383.TW", "2327.TW", "2303.TW", "2881.TW", "1303.TW"]
MARKET     = "^TWII"
START_DATE = "2010-01-01"

results = []
for ticker in TICKERS:
    print(f"正在處理 {ticker}...")
    res = process_ticker(ticker, MARKET, START_DATE)
    if res:
        results.append(res)

if not results:
    print("沒有任何股票處理成功。")
    exit()

# 彙整結果生成 HTML
all_sections = ""
summary_rows = ""

for res in results:
    ticker = res['ticker']
    signal = res['signal']
    latest_prob = res['latest_prob']
    threshold = res['threshold']
    latest_ret = res['latest_ret']
    latest_date = res['latest_date']
    history_df = res['history_df']
    history_proba = res['history_proba']

    alert_class = "" if signal else "safe"
    alert_title = "建議對沖" if signal else "正常持有"
    prob_color  = '#c0392b' if signal else '#27ae60'
    ret_color   = '#c0392b' if latest_ret < 0 else '#27ae60'
    ret_sign    = '+' if latest_ret >= 0 else ''
    gauge_color = 'linear-gradient(90deg,#f5a623,#c0392b)' if signal else 'linear-gradient(90deg,#27ae60,#2ecc71)'

    # 摘要表格行
    summary_rows += f"""
      <tr>
        <td><b>{ticker}</b></td>
        <td style="color:{prob_color}; font-weight:bold;">{latest_prob:.1%}</td>
        <td>{threshold:.1%}</td>
        <td><span class="badge {'hedge' if signal else 'hold'}">{alert_title}</span></td>
      </tr>
    """

    # 詳細區塊
    history_rows = ""
    for i in range(len(history_df) - 1, -1, -1):
        d_str = history_df.index[i].strftime("%Y-%m-%d")
        p = history_proba[i]
        r = history_df['Ret'].iloc[i]
        s = p >= threshold
        p_c = '#c0392b; font-weight:bold' if s else '#333'
        r_c = '#c0392b' if r < 0 else '#27ae60'
        r_s = '+' if r >= 0 else ''
        b = '<span class="badge hedge">對沖</span>' if s else '<span class="badge hold">持有</span>'
        history_rows += f"<tr><td>{d_str}</td><td style='color:{p_c};'>{p:.1%}</td><td style='color:{r_c};'>{r_s}{r:.1%}</td><td>{b}</td></tr>"

    all_sections += f"""
    <div class="section" id="section-{ticker}">
      <div class="section-title">{ticker} 詳細分析</div>
      <div class="metrics">
        <div class="metric">
          <div class="val" style="color:{prob_color};">{latest_prob:.1%}</div>
          <div class="lbl">風險機率</div>
        </div>
        <div class="metric">
          <div class="val">{threshold:.1%}</div>
          <div class="lbl">觸發門檻</div>
        </div>
        <div class="metric">
          <div class="val" style="color:{ret_color};">{ret_sign}{latest_ret:.1%}</div>
          <div class="lbl">上週報酬</div>
        </div>
      </div>
      <table class="history-table">
        <tr><th>週次</th><th>風險機率</th><th>上週報酬</th><th>訊號</th></tr>
        {history_rows}
      </table>
    </div>
    """

# 組裝最終 HTML
html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
  .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: #1a1a2e; color: white; padding: 28px 32px; }}
  .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 2px; color: #e0e0ff; }}
  .section {{ padding: 24px 32px; border-bottom: 1px solid #eee; }}
  .section-title {{ font-size: 14px; color: #333; font-weight:bold; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 18px; border-left: 4px solid #1a1a2e; padding-left: 10px; }}
  .metrics {{ display: flex; gap: 12px; margin-bottom: 15px; }}
  .metric {{ flex: 1; background: #f9f9f9; border-radius: 6px; padding: 12px; text-align: center; border: 1px solid #eee; }}
  .metric .val {{ font-size: 20px; font-weight: bold; }}
  .metric .lbl {{ font-size: 11px; color: #999; margin-top: 4px; }}
  .history-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  .history-table th {{ font-size: 11px; color: #999; text-align: left; padding: 8px 0; border-bottom: 1px solid #eee; }}
  .history-table td {{ font-size: 12px; color: #333; padding: 8px 0; border-bottom: 1px solid #f5f5f5; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }}
  .badge.hedge {{ background: #fff3cd; color: #856404; }}
  .badge.hold {{ background: #d4edda; color: #155724; }}
  .footer {{ padding: 16px 32px; background: #f9f9f9; font-size: 11px; color: #bbb; text-align: center; }}
  .summary-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  .summary-table th {{ background: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; }}
  .summary-table td {{ padding: 12px; border-bottom: 1px solid #dee2e6; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>多檔股票風險對沖通報</h1>
    <p>日期：{results[0]['latest_date'].strftime("%Y-%m-%d")} | XGBOOST TAIL RISK MODEL</p>
  </div>
  
  <div class="section">
    <div class="section-title">全體股票摘要</div>
    <table class="summary-table">
      <tr><th>股票代號</th><th>風險機率</th><th>觸發門檻</th><th>建議行動</th></tr>
      {summary_rows}
    </table>
  </div>

  {all_sections}

  <div class="footer">
    此報告由 XGBoost 模型自動生成，僅供參考，不構成投資建議。
  </div>
</div>
</body>
</html>"""

# =========================================================
# 5. 發送 Email
# =========================================================
try:
    sender   = os.environ["SENDER_EMAIL"]
    password = os.environ["SENDER_PASSWORD"]
    receiver = os.environ["RECEIVER_EMAIL"]

    hedge_count = sum(1 for r in results if r['signal'])
    subject = f"【風險對沖週報】{len(results)}檔監控中，{hedge_count}檔建議對沖 ({results[0]['latest_date'].strftime('%Y-%m-%d')})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f"通報發送完成：共 {len(results)} 檔股票，{hedge_count} 檔建議對沖。")
except KeyError:
    print("環境變數 SENDER_EMAIL, SENDER_PASSWORD 或 RECEIVER_EMAIL 未設置，跳過發送。")
    # 寫入本地文件供檢查
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("報告已儲存至 report.html")
