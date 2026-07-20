import json
import yfinance as yf
import pandas as pd
import numpy as np
import xgboost as xgb
import smtplib
import os
import subprocess
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# 1. 資料下載與清洗
# =========================================================
def get_cleaned_data(ticker, mkt_ticker, start):
    df_asset = yf.download(ticker, start=start, auto_adjust=True)
    df_mkt = yf.download(mkt_ticker, start=start, auto_adjust=True)

    if df_asset.empty or df_mkt.empty:
        return pd.DataFrame()

    if isinstance(df_asset.columns, pd.MultiIndex):
        df_asset.columns = [col[0] for col in df_asset.columns]
    if isinstance(df_mkt.columns, pd.MultiIndex):
        df_mkt.columns = [col[0] for col in df_mkt.columns]

    df_w = pd.DataFrame({
        "Close": df_asset["Close"].resample("W-FRI").last(),
        "Volume": df_asset["Volume"].resample("W-FRI").sum(),
        "Mkt_Close": df_mkt["Close"].resample("W-FRI").last(),
    }).dropna()

    return df_w

# =========================================================
# 2. 特徵工程
# =========================================================
def build_features(df):
    df = df.copy()
    df["Ret"] = df["Close"].pct_change()
    df["Mkt_Ret"] = df["Mkt_Close"].pct_change()
    df["Volat_4w"] = df["Ret"].rolling(4).std()
    df["Volat_12w"] = df["Ret"].rolling(12).std()
    df["Vol_Ratio"] = df["Volat_4w"] / (df["Volat_12w"] + 1e-6)
    df["MA_4"] = df["Close"].rolling(4).mean()
    df["MA_12"] = df["Close"].rolling(12).mean()
    df["Bias_4w"] = (df["Close"] - df["MA_4"]) / (df["MA_4"] + 1e-6)
    df["MA_Spread"] = (df["MA_4"] - df["MA_12"]) / (df["MA_12"] + 1e-6)
    df["Mom_4w"] = df["Close"].pct_change(4)
    df["Vol_Change"] = df["Volume"].pct_change()
    df["Ret_Lag1"] = df["Ret"].shift(1)
    df["Ret_Lag2"] = df["Ret"].shift(2)
    low_4w = df["Close"].rolling(4).min()
    df["Dist_Low_4w"] = (df["Close"] - low_4w) / (low_4w + 1e-6)

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()

    return df

# =========================================================
# 3. 核心處理邏輯
# =========================================================
def process_ticker(ticker, name, mkt_ticker, start_date):
    features = [
        "Volat_4w",
        "Vol_Ratio",
        "Bias_4w",
        "MA_Spread",
        "Mom_4w",
        "Vol_Change",
        "Ret_Lag1",
        "Ret_Lag2",
        "Dist_Low_4w",
    ]

    df_raw = get_cleaned_data(ticker, mkt_ticker, start_date)
    if df_raw.empty or len(df_raw) < 20:
        return None

    df_feat = build_features(df_raw)
    if len(df_feat) < 15:
        return None

    split_idx = int(len(df_feat) * 0.8)
    train_df = df_feat.iloc[:split_idx]

    # 這個門檻是「歷史週報酬最差 10%」的分界。
    # 例如 -5.3% 代表模型把單週跌幅超過 5.3% 視為尾部風險事件。
    downside_threshold = train_df["Ret"].quantile(0.10)
    y_train = (train_df["Ret"] < downside_threshold).astype(int)
    X_train = train_df[features]

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
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    all_proba = model.predict_proba(df_feat[features])[:, 1]
    probability_threshold = np.percentile(all_proba, 90)

    latest_prob = all_proba[-1]
    latest_date = df_feat.index[-1]
    latest_ret = df_feat["Ret"].iloc[-1]
    signal = latest_prob >= probability_threshold

    history_df = df_feat.iloc[-6:].copy()
    history_proba = all_proba[-6:]

    return {
        "ticker": ticker,
        "name": name,
        "latest_prob": latest_prob,
        "probability_threshold": probability_threshold,
        "downside_threshold": downside_threshold,
        "latest_date": latest_date,
        "latest_ret": latest_ret,
        "signal": signal,
        "history_df": history_df,
        "history_proba": history_proba,
    }

def format_downside_threshold(value):
    if value < 0:
        return f"跌超過 {abs(value):.1%}"
    return f"低於 {value:.1%}"

def pct_value(value):
    return round(float(value), 6)

def format_week_range(end_date):
    end_date = pd.Timestamp(end_date)
    start_date = end_date - pd.Timedelta(days=4)
    return f"{start_date.strftime('%Y-%m-%d')}～{end_date.strftime('%Y-%m-%d')}"

# =========================================================
# 4. 主程式
# =========================================================
STOCKS = {
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2317.TW": "鴻海",
    "3711.TW": "日月光",
    "2303.TW": "聯電",
    "2308.TW": "台達電",
    "2383.TW": "台光電",
    "2327.TW": "國巨",
    "1303.TW": "南亞",
    "2881.TW": "富邦金",
    "3037.TW": "欣興",
    "2409.TW": "友達",
    "3481.TW": "群創",
}
MARKET = "^TWII"
START_DATE = "2010-01-01"

results = []
for ticker, name in STOCKS.items():
    print(f"正在處理 {ticker} {name}...")
    res = process_ticker(ticker, name, MARKET, START_DATE)
    if res:
        results.append(res)

if not results:
    print("沒有任何股票處理成功。")
    exit()

report_items = []

for res in results:
    ticker = res["ticker"]
    name = res["name"]
    signal = res["signal"]
    latest_prob = res["latest_prob"]
    probability_threshold = res["probability_threshold"]
    downside_threshold = res["downside_threshold"]
    latest_ret = res["latest_ret"]
    latest_date = res["latest_date"]
    history_df = res["history_df"]
    history_proba = res["history_proba"]

    threshold_text = format_downside_threshold(downside_threshold)
    history_items = []
    for i in range(len(history_df) - 1, -1, -1):
        probability = history_proba[i]
        weekly_return = history_df["Ret"].iloc[i]
        history_signal = probability >= probability_threshold
        history_items.append({
            "date": format_week_range(history_df.index[i]),
            "riskProbability": pct_value(probability),
            "weeklyReturn": pct_value(weekly_return),
            "signal": bool(history_signal),
            "action": "對沖" if history_signal else "持有",
        })

    report_items.append({
        "ticker": ticker,
        "name": name,
        "latestDate": latest_date.strftime("%Y-%m-%d"),
        "latestWeekRange": format_week_range(latest_date),
        "riskProbability": pct_value(latest_prob),
        "probabilityThreshold": pct_value(probability_threshold),
        "downsideThreshold": pct_value(downside_threshold),
        "downsideThresholdText": threshold_text,
        "weeklyReturn": pct_value(latest_ret),
        "signal": bool(signal),
        "action": "建議對沖" if signal else "正常持有",
        "history": history_items,
    })

hedge_count = sum(1 for r in results if r["signal"])
report_data = {
    "title": "台股尾部風險對沖通報",
    "latestDate": results[0]["latest_date"].strftime("%Y-%m-%d"),
    "latestWeekRange": format_week_range(results[0]["latest_date"]),
    "model": "XGBoost Tail Risk Model",
    "market": MARKET,
    "stockCount": len(report_items),
    "hedgeCount": hedge_count,
    "stocks": report_items,
    "disclaimer": "此報告由 XGBoost 模型自動生成，僅供研究與風險控管參考，不構成投資建議。",
}

public_dir = Path("public")
public_dir.mkdir(exist_ok=True)
with open(public_dir / "report-data.json", "w", encoding="utf-8") as f:
    json.dump(report_data, f, ensure_ascii=False, indent=2)
print("網站資料已儲存至 public/report-data.json")

template_path = Path(__file__).with_name("email-template.js")
template_result = subprocess.run(
    ["node", str(template_path)],
    input=json.dumps(report_data, ensure_ascii=False),
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=True,
)
html = template_result.stdout
print("Email HTML 已由 email-template.js 產生")

# =========================================================
# 5. 發送 Email
# =========================================================
try:
    sender = os.environ["SENDER_EMAIL"]
    password = os.environ["SENDER_PASSWORD"]
    receiver = os.environ["RECEIVER_EMAIL"]

    subject = f"【風險對沖週報】{len(results)}檔監控中，{hedge_count}檔建議對沖 ({format_week_range(results[0]['latest_date'])})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f"通報發送完成：共 {len(results)} 檔股票，{hedge_count} 檔建議對沖。")
except KeyError:
    print("環境變數 SENDER_EMAIL, SENDER_PASSWORD 或 RECEIVER_EMAIL 未設置，跳過發送。")
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("報告已儲存至 report.html")
