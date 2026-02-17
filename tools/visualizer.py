import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

# 導航修正
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings

def run_visualizer():
    # 1. 讀取兩份資料
    history_path = "data/history/TMF_FULL_REPLAY.csv"
    trade_log_path = "data/backtest_detail.csv"
    
    if not os.path.exists(history_path) or not os.path.exists(trade_log_path):
        print("❌ 找不到資料檔，請確認 history_merger.py 和 backtest.py 都跑過。")
        return

    print("📖 正在載入歷史數據與交易紀錄...")
    
    # 💡 格式轉換：處理 TIMEFRAME (例如把 30 轉成 "30min")
    raw_tf = str(Settings.TIMEFRAME)
    if "min" not in raw_tf and "T" not in raw_tf:
        resample_freq = f"{raw_tf}min"
    else:
        resample_freq = raw_tf

    print(f"⚙️ 使用重採樣頻率: {resample_freq}")

    # A. 處理價格數據 (重採樣為 30min 以匹配策略)
    df_price = pd.read_csv(history_path)
    df_price['Time'] = pd.to_datetime(df_price['Time'])
    df_price.set_index('Time', inplace=True)
    
    # 使用轉換後的 resample_freq
    df_30 = df_price.resample(resample_freq).agg({'Close': 'last'}).dropna()
    
    # 計算均線 (畫圖用)
    df_30['MA_Short'] = df_30['Close'].rolling(window=Settings.SHORT_P).mean()
    df_30['MA_Long'] = df_30['Close'].rolling(window=Settings.LONG_P).mean()

    # B. 處理交易紀錄
    df_trade = pd.read_csv(trade_log_path)
    df_trade['Time'] = pd.to_datetime(df_trade['Time'])
    df_trade.set_index('Time', inplace=True)

    # 2. 開始繪圖 (建立 3 個子圖)
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True, 
                                        gridspec_kw={'height_ratios': [3, 1.5, 1]})

    # --- 第一層：K線 (收盤價) 與 均線 ---
    ax1.set_title(f'TMF Strategy Visualization (MA {Settings.SHORT_P}/{Settings.LONG_P}, Stop: {Settings.STOP_LOSS})', fontsize=14)
    ax1.plot(df_30.index, df_30['Close'], label='Close Price', color='gray', alpha=0.5, lw=1)
    
    # 畫均線
    ax1.plot(df_30.index, df_30['MA_Short'], label=f'MA {Settings.SHORT_P}', color='#ff7f0e', lw=1.5) # Orange
    ax1.plot(df_30.index, df_30['MA_Long'], label=f'MA {Settings.LONG_P}', color='#1f77b4', lw=1.5)  # Blue

    # 標記買賣點
    # 這裡用 try-except 避免如果沒有某一類交易時報錯
    try:
        buys = df_trade[df_trade['Action'].str.contains('BUY', na=False)]
        sells = df_trade[df_trade['Action'].str.contains('SELL', na=False)]
        exits = df_trade[df_trade['Action'].str.contains('EXIT', na=False)]
        stops = df_trade[df_trade['Action'].str.contains('STOP', na=False)]

        if not buys.empty:
            ax1.scatter(buys.index, buys['Price'], marker='^', color='green', s=100, label='Buy', zorder=5)
        if not sells.empty:
            ax1.scatter(sells.index, sells['Price'], marker='v', color='red', s=100, label='Sell', zorder=5)
        if not exits.empty:
            ax1.scatter(exits.index, exits['Price'], marker='o', color='black', s=50, label='Normal Exit', zorder=5)
        if not stops.empty:
            ax1.scatter(stops.index, stops['Price'], marker='x', color='red', s=150, linewidths=3, label='Stop Loss', zorder=6)
    except Exception as e:
        print(f"⚠️ 標記點位時發生小問題 (不影響畫圖): {e}")

    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # --- 第二層：資產曲線 (Equity) ---
    ax2.step(df_trade.index, df_trade['equity'], where='post', color='#2ca02c', lw=2)
    ax2.set_ylabel('Net Equity (Pts)')
    ax2.set_title('Realized Equity Curve', fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    # --- 第三層：回撤 (Drawdown) ---
    ax3.fill_between(df_trade.index, df_trade['drawdown'], 0, color='#d62728', alpha=0.4, step='post')
    ax3.set_ylabel('Drawdown')
    ax3.set_xlabel('Time')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = "data/strategy_full_view.png"
    plt.savefig(output_path)
    print(f"✅ 完整分析圖已生成：{output_path}")
    
    # 在某些環境下如果沒安裝圖形介面，show() 可能會卡住，這裡保留但不強制
    try:
        plt.show()
    except:
        pass

if __name__ == "__main__":
    run_visualizer()