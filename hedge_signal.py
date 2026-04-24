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
test_df   = df_feat.iloc[split_idx:]

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

# 用全部資料的最後一筆作為本週訊號
latest = df_feat[features].iloc[[-1]]
latest_date = df_feat.index[-1]
latest_prob = model.predict_proba(latest)[0][1]

# 觸發門檻：訓練集預測機率的 90th percentile
X_all   = df_feat[features]
all_prob = model.predict_proba(X_all)[:, 1]
threshold = np.percentile(all_prob, 90)

signal = latest_prob >= threshold
latest_ret = df_feat['Ret'].iloc[-1]

# =========================================================
# 4. 發送 Email
# =========================================================
sender   = os.environ["SENDER_EMAIL"]
password = os.environ["SENDER_PASSWORD"]
receiver = os.environ["RECEIVER_EMAIL"]

subject = f"【{ASSET} 週報】{'⚠️ 本週建議啟動期貨對沖' if signal else '✅ 本週無需對沖，正常持有'}"

feature_rows = ""
for f in features:
    feature_rows += f"<tr><td>{f}</td><td>{latest[f].values[0]:.6f}</td></tr>"

html = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
  <h2>{ASSET} 本週對沖訊號報告</h2>
  <p>資料日期：{latest_date.date()}</p>

  <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
    <tr style="background:#f0f0f0;">
      <td><b>本週訊號</b></td>
      <td><b>{'⚠️ 建議啟動期貨對沖' if signal else '✅ 無需對沖，正常持有'}</b></td>
    </tr>
    <tr>
      <td>尾部風險機率</td>
      <td>{latest_prob:.2%}</td>
    </tr>
    <tr>
      <td>觸發門檻</td>
      <td>{threshold:.2%}</td>
    </tr>
    <tr>
      <td>上週報酬率</td>
      <td>{latest_ret:.2%}</td>
    </tr>
  </table>

  <br>
  <h3>模型特徵數值（供參考）</h3>
  <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
    <tr style="background:#f0f0f0;">
      <th>特徵</th><th>數值</th>
    </tr>
    {feature_rows}
  </table>
</body>
</html>
"""

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"]    = sender
msg["To"]      = receiver
msg.attach(MIMEText(html, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(sender, password)
    server.sendmail(sender, receiver, msg.as_string())

print(f"訊號發送完成：{'建議對沖' if signal else '無需對沖'}，風險機率 {latest_prob:.2%}")
