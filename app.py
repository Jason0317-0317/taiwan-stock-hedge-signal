import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import urllib.request, os
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from sklearn.metrics import (f1_score, precision_score, recall_score,
                             roc_auc_score, brier_score_loss, confusion_matrix)

# 字體設置
font_path = "/tmp/NotoSansTC.otf"
if not os.path.exists(font_path):
    try:
        urllib.request.urlretrieve(
            "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf",
            font_path
        )
    except:
        pass

if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
else:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# =========================================================
# 1. 資料下載與清洗
# =========================================================
def get_cleaned_data(ticker, mkt_ticker, start):
    df = yf.download([ticker, mkt_ticker], start=start, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        # 處理 yfinance 多索引列名
        cols = []
        for col in df.columns:
            if col[1] == ticker:
                cols.append(f"{col[0]}_ASSET")
            elif col[1] == mkt_ticker:
                cols.append(f"{col[0]}_MKT")
            else:
                cols.append(f"{col[0]}_{col[1]}")
        df.columns = cols
    else:
        # 如果不是 MultiIndex，則假設列名已經是 Close, Volume 等
        # 這種情況較少見於下載多個 ticker
        pass

    try:
        asset_close = df["Close_ASSET"]
        asset_vol   = df["Volume_ASSET"]
        mkt_close   = df["Close_MKT"]
    except KeyError:
        # 備用方案
        return pd.DataFrame()

    df_w = pd.DataFrame({
        'Close':     asset_close.resample('W-FRI').last(),
        'Volume':    asset_vol.resample('W-FRI').sum(),
        'Mkt_Close': mkt_close.resample('W-FRI').last()
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
# 3. Streamlit UI
# =========================================================
st.set_page_config(page_title="多檔股票風險對沖分析", layout="wide")
st.title("XGBoost 尾部風險對沖策略分析")

TICKERS_MAP = {
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2308.TW": "台達電",
    "2317.TW": "鴻海",
    "3711.TW": "日月光",
    "2383.TW": "台光電",
    "2327.TW": "國巨",
    "2303.TW": "聯電",
    "2881.TW": "富邦金",
    "1303.TW": "南亞",
    "3037.TW": "欣興",
    "2409.TW": "友達",
    "3481.TW": "群創"
}

selected_ticker = st.sidebar.selectbox("選擇股票", list(TICKERS_MAP.keys()), format_func=lambda x: f"{x} {TICKERS_MAP[x]}")

MARKET     = "^TWII"
START_DATE = "2010-01-01"

FUTURES_COMMISSION = 0.0004
FUTURES_SLIPPAGE   = 0.0002
FUTURES_CARRY_RATE = 0.02
HEDGE_RATIO        = 1.0
WEEKS_PER_YEAR     = 52
WEEKLY_CARRY   = FUTURES_CARRY_RATE / WEEKS_PER_YEAR
OPEN_CLOSE_COST = (FUTURES_COMMISSION + FUTURES_SLIPPAGE) * 2

with st.spinner(f"正在分析 {selected_ticker}..."):
    df_raw = get_cleaned_data(selected_ticker, MARKET, START_DATE)
    if df_raw.empty:
        st.error("無法下載資料，請檢查網路或稍後再試。")
        st.stop()
    
    df_feat = build_features(df_raw)
    if len(df_feat) < 50:
        st.error("資料筆數不足以進行訓練。")
        st.stop()

    split_idx  = int(len(df_feat) * 0.8)
    train_df   = df_feat.iloc[:split_idx]
    test_df    = df_feat.iloc[split_idx:]

    risk_threshold = train_df['Ret'].quantile(0.10)
    
    y_train = (train_df['Ret'] < risk_threshold).astype(int)
    y_test  = (test_df['Ret'] < risk_threshold).astype(int)

    features = ['Volat_4w', 'Vol_Ratio', 'Bias_4w', 'MA_Spread',
                'Mom_4w', 'Vol_Change', 'Ret_Lag1', 'Ret_Lag2', 'Dist_Low_4w']
    X_train  = train_df[features]
    X_test   = test_df[features]

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

    y_proba          = model.predict_proba(X_test)[:, 1]
    top_10_threshold = np.percentile(y_proba, 90)
    y_pred_hedge     = (y_proba >= top_10_threshold).astype(int)

    # 顯示指標
    st.subheader(f"{selected_ticker} {TICKERS_MAP[selected_ticker]} 評估報告")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROC-AUC", f"{roc_auc_score(y_test, y_proba):.4f}")
    c2.metric("Precision", f"{precision_score(y_test, y_pred_hedge):.4f}")
    c3.metric("Recall", f"{recall_score(y_test, y_pred_hedge):.4f}")
    c4.metric("F1 Score", f"{f1_score(y_test, y_pred_hedge):.4f}")

    # 回測
    ret_test = test_df['Ret'].values
    signal   = pd.Series(y_pred_hedge, index=test_df.index)
    
    hedge_ret = []
    prev_s = 0
    for r, s in zip(ret_test, signal):
        cost = OPEN_CLOSE_COST if s != prev_s else 0
        if s == 1:
            net = r - HEDGE_RATIO * r - WEEKLY_CARRY - cost
        else:
            net = r - cost
        hedge_ret.append(net)
        prev_s = s
    
    hedge_ret = np.array(hedge_ret)
    cum_bh = (1 + ret_test).cumprod() - 1
    cum_hedge = (1 + hedge_ret).cumprod() - 1
    
    # 績效表
    st.subheader("策略績效")
    perf_df = pd.DataFrame({
        "指標": ["總報酬率", "最大回撤", "對沖比例"],
        "買進持有": [f"{cum_bh[-1]:.2%}", f"{( (1+cum_bh) / (1+cum_bh).cummax() - 1 ).min():.2%}", "0%"],
        "期貨對沖": [f"{cum_hedge[-1]:.2%}", f"{( (1+cum_hedge) / (1+cum_hedge).cummax() - 1 ).min():.2%}", f"{signal.mean():.1%}"]
    })
    st.table(perf_df)

    # 圖表
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(test_df.index, cum_bh * 100, label="買進持有")
    ax.plot(test_df.index, cum_hedge * 100, label="期貨對沖")
    ax.fill_between(test_df.index, 0, 1, where=signal==1, color='red', alpha=0.1, transform=ax.get_xaxis_transform(), label="對沖區間")
    ax.set_ylabel("累積報酬 (%)")
    ax.legend()
    st.pyplot(fig)
