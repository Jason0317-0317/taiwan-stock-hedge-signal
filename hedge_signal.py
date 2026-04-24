import yfinance as yf
import pandas as pd
import numpy as np
import xgboost as xgb
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# 1. 資料下載與清洗
# =========================================================
def get_cleaned_data(ticker, mkt_ticker, start):
    df_asset = yf.download(ticker, start=start, auto_adjust=True)
    df_mkt   = yf.download(mkt_ticker, start=start, auto_adjust=True)

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
    df['Bias_4w']    = (df['Close'] - df['MA_4']) / df['MA_4']
    df['MA_Spread']  = (df['MA_4'] - df['MA_12']) / df['MA_12']
    df['Mom_4w']     = df['Close'].pct_change(4)
    df['Vol_Change'] = df['Volume'].pct_change()
    df['Ret_Lag1']   = df['Ret'].shift(1)
    df['Ret_Lag2']   = df['Ret'].shift(2)
    low_4w           = df['Close'].rolling(4).min()
    df['Dist_Low_4w']= (df['Close'] - low_4w) / low_4w

    return df.dropna()

# =========================================================
# 3. 主程式
# =========================================================
ASSET      = "2330.TW"
MARKET     = "^TWII"
START_DATE = "2010-01-01"

features = ['Volat_4w', 'Vol_Ratio', 'Bias_4w', 'MA_Spread',
            'Mom_4w', 'Vol_Change', 'Ret_Lag1', 'Ret_Lag2', 'Dist_Low_4w']

df_raw  = get_cleaned_data(ASSET, MARKET, START_DATE)
df_feat = build_features(df_raw)

split_idx = int(len(df_feat) * 0.8)
train_df  = df_feat.iloc[:split_idx]

risk_threshold = train_df['Ret'].quantile(0.10)
y_train = (train_df['Ret'] < risk_threshold).astype(int)
X_train = train_df[features]

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

# 觸發門檻：全資料預測機率的 90th percentile
all_proba = model.predict_proba(df_feat[features])[:, 1]
threshold = np.percentile(all_proba, 90)

# 本週訊號
latest_prob = all_proba[-1]
latest_date = df_feat.index[-1]
latest_ret  = df_feat['Ret'].iloc[-1]
signal      = latest_prob >= threshold

# 近6週歷史
history_df = df_feat.iloc[-6:].copy()
history_proba = all_proba[-6:]
history_rows = ""
for i in range(len(history_df) - 1, -1, -1):
    date  = history_df.index[i].strftime("%Y-%m-%d")
    prob  = history_proba[i]
    ret   = history_df['Ret'].iloc[i]
    sig   = prob >= threshold

    prob_color = '#c0392b; font-weight:bold' if sig else '#333'
    ret_color  = '#c0392b' if ret < 0 else '#27ae60'
    ret_sign   = '+' if ret >= 0 else ''
    badge      = '<span class="badge hedge">對沖</span>' if sig else '<span class="badge hold">持有</span>'

    history_rows += f"""
      <tr>
        <td>{date}</td>
        <td style="color:{prob_color};">{prob:.1%}</td>
        <td style="color:{ret_color};">{ret_sign}{ret:.1%}</td>
        <td>{badge}</td>
      </tr>
    """

# =========================================================
# 4. 組裝 HTML Email
# =========================================================
alert_class = "" if signal else "safe"
alert_title = "本週建議啟動期貨對沖" if signal else "本週無需對沖，正常持有"
alert_sub   = f"尾部風險機率 {latest_prob:.1%}，{'超過' if signal else '低於'}觸發門檻 {threshold:.1%}"
prob_color  = '#c0392b' if signal else '#27ae60'
ret_color   = '#c0392b' if latest_ret < 0 else '#27ae60'
ret_sign    = '+' if latest_ret >= 0 else ''
gauge_color = 'linear-gradient(90deg,#f5a623,#c0392b)' if signal else 'linear-gradient(90deg,#27ae60,#2ecc71)'

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
  .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: #1a1a2e; color: white; padding: 28px 32px; }}
  .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 2px; color: #e0e0ff; }}
  .header p {{ margin: 8px 0 0; color: #666; font-size: 12px; letter-spacing: 1px; }}
  .alert {{ padding: 20px 32px; background: #fff3cd; border-left: 5px solid #f5a623; }}
  .alert.safe {{ background: #d4edda; border-left-color: #28a745; }}
  .alert-title {{ font-size: 18px; font-weight: bold; color: #856404; }}
  .alert.safe .alert-title {{ color: #155724; }}
  .alert-sub {{ font-size: 13px; color: #666; margin-top: 4px; }}
  .section {{ padding: 24px 32px; border-bottom: 1px solid #eee; }}
  .section-title {{ font-size: 11px; color: #999; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 18px; }}
  .metrics {{ display: flex; gap: 12px; }}
  .metric {{ flex: 1; background: #f9f9f9; border-radius: 6px; padding: 16px; text-align: center; border: 1px solid #eee; }}
  .metric .val {{ font-size: 28px; font-weight: bold; }}
  .metric .lbl {{ font-size: 11px; color: #999; margin-top: 6px; }}
  .gauge-track {{ background: #f0f0f0; border-radius: 6px; height: 22px; position: relative; margin: 8px 0 20px; }}
  .gauge-fill {{ height: 22px; border-radius: 6px; position: relative; }}
  .gauge-fill span {{ position: absolute; right: 10px; top: 3px; font-size: 12px; color: white; font-weight: bold; }}
  .gauge-marker {{ position: absolute; top: -6px; width: 2px; height: 34px; background: #333; opacity: 0.4; }}
  .gauge-marker-label {{ font-size: 10px; color: #999; margin-top: 4px; }}
  .history-table {{ width: 100%; border-collapse: collapse; }}
  .history-table th {{ font-size: 11px; color: #999; text-align: left; padding: 8px 0; border-bottom: 1px solid #eee; letter-spacing: 1px; text-transform: uppercase; }}
  .history-table td {{ font-size: 13px; color: #333; padding: 10px 0; border-bottom: 1px solid #f5f5f5; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
  .badge.hedge {{ background: #fff3cd; color: #856404; }}
  .badge.hold {{ background: #d4edda; color: #155724; }}
  .footer {{ padding: 16px 32px; background: #f9f9f9; font-size: 11px; color: #bbb; text-align: center; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>2330.TW / HEDGE SIGNAL REPORT</h1>
    <p>WEEK OF {latest_date.strftime("%Y-%m-%d")} &nbsp;|&nbsp; XGBOOST TAIL RISK MODEL</p>
  </div>

  <div class="alert {alert_class}">
    <div class="alert-title">{alert_title}</div>
    <div class="alert-sub">{alert_sub}</div>
  </div>

  <div class="section">
    <div class="section-title">核心指標</div>
    <div class="metrics">
      <div class="metric">
        <div class="val" style="color:{prob_color};">{latest_prob:.1%}</div>
        <div class="lbl">本週尾部風險機率</div>
      </div>
      <div class="metric">
        <div class="val">{threshold:.1%}</div>
        <div class="lbl">觸發門檻</div>
      </div>
      <div class="metric">
        <div class="val" style="color:{ret_color};">{ret_sign}{latest_ret:.1%}</div>
        <div class="lbl">上週報酬率</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">風險機率儀表</div>
    <div style="display:flex; align-items:center; gap:12px; margin: 8px 0 4px;">
      <div class="gauge-track" style="flex:1; margin:0; position:relative;">
        <div class="gauge-fill" style="width:{min(latest_prob*100, 100):.1f}%; background:{gauge_color}; height:22px; border-radius:6px;"></div>
        <div class="gauge-marker" style="left:{threshold*100:.1f}%;"></div>
      </div>
      <div style="font-size:15px; font-weight:bold; color:{prob_color}; white-space:nowrap; min-width:48px;">{latest_prob:.1%}</div>
    </div>
    <div class="gauge-marker-label" style="padding-left:calc({threshold*100:.1f}% - 16px);">門檻 {threshold:.1%}</div>
  </div>

  <div class="section">
    <div class="section-title">近6週訊號歷史</div>
    <table class="history-table">
      <tr>
        <th>週次</th>
        <th>風險機率</th>
        <th>上週報酬</th>
        <th>訊號</th>
      </tr>
      {history_rows}
    </table>
  </div>

  <div class="footer">
    此報告由 XGBoost 模型自動生成，僅供參考，不構成投資建議。
  </div>

</div>
</body>
</html>"""

# =========================================================
# 5. 發送 Email
# =========================================================
sender   = os.environ["SENDER_EMAIL"]
password = os.environ["SENDER_PASSWORD"]
receiver = os.environ["RECEIVER_EMAIL"]

subject = f"【2330.TW 週報】{'本週建議啟動期貨對沖' if signal else '本週無需對沖，正常持有'} ({latest_date.strftime('%Y-%m-%d')})"

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = sender
msg["To"]      = receiver
msg.attach(MIMEText(html, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(sender, password)
    server.sendmail(sender, receiver, msg.as_string())

print(f"訊號發送完成：{'建議對沖' if signal else '無需對沖'}，風險機率 {latest_prob:.1%}")
