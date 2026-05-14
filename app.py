import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from sklearn.metrics import (f1_score, precision_score, recall_score,
                             roc_auc_score, brier_score_loss, confusion_matrix)

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# =========================================================
# 1. 資料下載與清洗 (Data Acquisition)
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
})
def get_cleaned_data(ticker, mkt_ticker, start):
    df = yf.download([ticker, mkt_ticker], start=start, auto_adjust=True, session=session)
    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        if 'Close' in df.columns.get_level_values(0):
            df.columns = [f"{col[0]}_{col[1]}" for col in df.columns]
        else:
            df.columns = [f"{col[1]}_{col[0]}" for col in df.columns]

    asset_close = df[f"Close_{ticker}"]
    asset_vol   = df[f"Volume_{ticker}"]
    mkt_close   = df[f"Close_{mkt_ticker}"]

    df_w = pd.DataFrame({
        'Close':     asset_close.resample('W-FRI').last(),
        'Volume':    asset_vol.resample('W-FRI').sum(),
        'Mkt_Close': mkt_close.resample('W-FRI').last()
    }).dropna()

    return df_w

# =========================================================
# 2. 特徵工程 (Feature Engineering)
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
# 3. 執行主程式
# =========================================================
ASSET      = "2330.TW"
MARKET     = "^TWII"
START_DATE = "2010-01-01"

FUTURES_COMMISSION = 0.0004
FUTURES_SLIPPAGE   = 0.0002
FUTURES_CARRY_RATE = 0.02
HEDGE_RATIO        = 1.0
WEEKS_PER_YEAR     = 52

WEEKLY_CARRY   = FUTURES_CARRY_RATE / WEEKS_PER_YEAR
OPEN_CLOSE_COST = (FUTURES_COMMISSION + FUTURES_SLIPPAGE) * 2

st.title(f"{ASSET} 買進持有 vs 期貨對沖策略比較")
with st.spinner("下載資料中..."):
    df_raw = get_cleaned_data(ASSET, MARKET, START_DATE)
    if df_raw.empty:
        st.error("無法從 Yahoo Finance 下載資料。這通常是因為 Streamlit Cloud 的 IP 遭到短暫阻擋，請稍後再試。")
        st.stop() # 停止執行後續程式碼，避免出現 IndexError
    df_feat = build_features(df_raw)
    if len(df_feat) < 50:
        st.error(f"資料筆數不足！清洗後僅剩 {len(df_feat)} 筆，無法進行機器學習訓練與切分。")
        st.stop()
with st.spinner("下載資料中..."):
    df_raw  = get_cleaned_data(ASSET, MARKET, START_DATE)
    df_feat = build_features(df_raw)

split_idx  = int(len(df_feat) * 0.8)
train_df   = df_feat.iloc[:split_idx]
test_df    = df_feat.iloc[split_idx:]

risk_threshold = train_df['Ret'].quantile(0.10)
st.write(f"定義尾部風險閾值 (訓練集 10% 分位數): {risk_threshold:.2%}")

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

# =========================================================
# 4. 效能評估 (Evaluation)
# =========================================================
st.subheader(f"評估報告: {ASSET} 尾部風險預測")

col1, col2, col3, col4 = st.columns(4)
col1.metric("ROC-AUC Score", f"{roc_auc_score(y_test, y_proba):.4f}")
col2.metric("Precision (對沖精準度)", f"{precision_score(y_test, y_pred_hedge):.4f}")
col3.metric("Recall (風險覆蓋率)", f"{recall_score(y_test, y_pred_hedge):.4f}")
col4.metric("F1 Score", f"{f1_score(y_test, y_pred_hedge):.4f}")

st.write("混淆矩陣 (預測對沖 vs 實際暴跌):")
st.dataframe(pd.DataFrame(confusion_matrix(y_test, y_pred_hedge),
                           index=["實際正常", "實際暴跌"],
                           columns=["預測正常", "預測對沖"]))

importance = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)
st.write("特徵重要性 Top 5:")
st.dataframe(importance.head(5).rename("重要性"))

# =========================================================
# 5. 策略回測：買進持有 vs 期貨對沖 (Backtest)
# =========================================================
ret_test = test_df['Ret'].values
signal   = pd.Series(y_pred_hedge, index=test_df.index)

hedge_ret   = []
spot_leg    = []
futures_leg = []
prev_signal = 0

for r, s in zip(ret_test, signal):
    if s == 1:
        switch_cost = OPEN_CLOSE_COST if prev_signal == 0 else 0.0
        spot_r    = r
        futures_r = -HEDGE_RATIO * r
        carry     = -WEEKLY_CARRY
        net       = spot_r + futures_r + carry - switch_cost

        spot_leg.append(spot_r)
        futures_leg.append(futures_r + carry - switch_cost)
        hedge_ret.append(net)
    else:
        switch_cost = OPEN_CLOSE_COST if prev_signal == 1 else 0.0
        spot_leg.append(r)
        futures_leg.append(-switch_cost)
        hedge_ret.append(r - switch_cost)

    prev_signal = s

hedge_ret   = np.array(hedge_ret)
spot_leg    = np.array(spot_leg)
futures_leg = np.array(futures_leg)

cum_bh    = (1 + ret_test).cumprod() - 1
cum_hedge = (1 + hedge_ret).cumprod() - 1
dates     = test_df.index

# =========================================================
# 6. 績效統計 (Performance Summary)
# =========================================================
def max_drawdown(cum_ret):
    wealth = 1 + cum_ret
    peak   = np.maximum.accumulate(wealth)
    dd     = (wealth - peak) / peak
    return dd.min()

def sharpe_ratio(ret, periods=52):
    if ret.std() == 0:
        return 0
    return (ret.mean() / ret.std()) * np.sqrt(periods)

total_bh      = cum_bh[-1]
total_hedge   = cum_hedge[-1]
mdd_bh        = max_drawdown(cum_bh)
mdd_hedge     = max_drawdown(cum_hedge)
sr_bh         = sharpe_ratio(ret_test)
sr_hedge      = sharpe_ratio(hedge_ret)
hedge_weeks   = signal.sum()
total_weeks   = len(signal)
total_carry   = hedge_weeks * WEEKLY_CARRY
n_switches    = int((signal.diff().abs()).sum())
total_tx_cost = n_switches * OPEN_CLOSE_COST

st.subheader("策略績效比較 (測試集期間)")
perf_df = pd.DataFrame({
    "指標": ["總報酬率", "最大回撤", "年化 Sharpe", "對沖觸發週數", "對沖觸發比例", "訊號切換次數", "總交易成本", "總持倉成本 (carry)"],
    "買進持有": [f"{total_bh:.2%}", f"{mdd_bh:.2%}", f"{sr_bh:.4f}", "—", "—", "—", "—", "—"],
    "期貨對沖": [f"{total_hedge:.2%}", f"{mdd_hedge:.2%}", f"{sr_hedge:.4f}",
                f"{int(hedge_weeks)}週", f"{hedge_weeks/total_weeks:.2%}",
                f"{n_switches}次", f"{total_tx_cost:.4%}", f"{total_carry:.4%}"]
}).set_index("指標")
st.dataframe(perf_df)

# =========================================================
# 7. 視覺化 (Visualization)
# =========================================================
fig, axes = plt.subplots(2, 1, figsize=(14, 12),
                         gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
fig.suptitle(f'{ASSET}  買進持有 vs 期貨對沖策略比較\n(測試集: {dates[0].date()} → {dates[-1].date()})',
             fontsize=14, fontweight='bold', y=0.98)

ax1 = axes[0]
ax1.plot(dates, cum_bh    * 100, label='買進持有 (Buy & Hold)',
         color='#4C78A8', linewidth=2)
ax1.plot(dates, cum_hedge * 100, label='期貨對沖 (Futures Hedged)',
         color='#F58518', linewidth=2)
ax1.axhline(0, color='gray', linewidth=0.8, linestyle='--')

in_hedge = False
start_h  = None
for i, (d, s) in enumerate(zip(dates, signal)):
    if s == 1 and not in_hedge:
        start_h  = d
        in_hedge = True
    elif s == 0 and in_hedge:
        ax1.axvspan(start_h, d, alpha=0.15, color='red', label='_nolegend_')
        in_hedge = False
if in_hedge:
    ax1.axvspan(start_h, dates[-1], alpha=0.15, color='red')

hedge_patch = Patch(facecolor='red', alpha=0.15, label='期貨空單對沖區間')
handles, labels = ax1.get_legend_handles_labels()
ax1.legend(handles + [hedge_patch], labels + ['期貨空單對沖區間'],
           fontsize=10, loc='upper left')

ax1.set_ylabel('累積報酬率 (%)', fontsize=11)
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))
ax1.set_title('累積報酬率比較', fontsize=12)
ax1.grid(True, alpha=0.3)

ax1.annotate(f'期貨對沖: {total_hedge:.1%}',
             xy=(dates[-1], cum_hedge[-1]*100),
             xytext=(8, 0), textcoords='offset points',
             color='#F58518', fontsize=9, va='center')
ax1.annotate(f'買進持有: {total_bh:.1%}',
             xy=(dates[-1], cum_bh[-1]*100),
             xytext=(8, 0), textcoords='offset points',
             color='#4C78A8', fontsize=9, va='center')

ax2 = axes[1]
wealth_bh    = 1 + cum_bh
wealth_hedge = 1 + cum_hedge
dd_bh    = (wealth_bh    - np.maximum.accumulate(wealth_bh))    / np.maximum.accumulate(wealth_bh)
dd_hedge = (wealth_hedge - np.maximum.accumulate(wealth_hedge)) / np.maximum.accumulate(wealth_hedge)

ax2.fill_between(dates, dd_bh    * 100, 0, alpha=0.4, color='#4C78A8', label='買進持有回撤')
ax2.fill_between(dates, dd_hedge * 100, 0, alpha=0.4, color='#F58518', label='期貨對沖回撤')
ax2.legend(fontsize=9, loc='lower left')
ax2.set_ylabel('回撤 (%)', fontsize=11)
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))
ax2.set_title('水下回撤比較', fontsize=12)
ax2.grid(True, alpha=0.3)
ax2.set_xlabel('日期', fontsize=11)

plt.tight_layout(rect=[0, 0, 1, 0.97])
st.pyplot(fig)
