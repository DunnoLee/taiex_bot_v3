import pandas as pd
import numpy as np
import os
import sys

# 導航修正
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings

def run_deep_analysis():
    file_path = "data/backtest_results/backtest_log.csv"
    if not os.path.exists(file_path):
        print("❌ 找不到 backtest_detail.csv，請先執行最新版 main_backtest.py")
        return

    df = pd.read_csv(file_path)
    df['Time'] = pd.to_datetime(df['Time'])

    # 1. 提取每筆已實現損益 (只要 equity 有變動的地方)
    # 這裡我們計算 equity 的差值來取得單筆損益
    pnl_series = df['equity'].diff().dropna()
    pnl_series = pnl_series[pnl_series != 0] # 只看有變動的筆數

    wins = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series < 0]

    # 2. 核心數據計算
    total_trades = len(pnl_series)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    avg_win = wins.mean() if not wins.empty else 0
    avg_loss = abs(losses.mean()) if not losses.empty else 0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 期待值 (Expectancy): 每一筆交易預期能賺幾點
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # 總淨利 (最終 Equity)
    net_profit = df['equity'].iloc[-1]
    mdd = df['drawdown'].min()

    # 3. 輸出報表
    print(f"\n📈 --- 策略大腦深度診斷報告 (TF: {Settings.TIMEFRAME}) ---")
    print("-" * 45)
    print(f"✅ 總交易筆數: {total_trades:>10} 筆")
    print(f"🎯 勝    率: {win_rate*100:>10.2f} %")
    print(f"💰 平均獲利: {avg_win:>10.2f} 點")
    print(f"💸 平均虧損: {avg_loss:>10.2f} 點")
    print(f"⚖️ 賺賠比 (RR): {rr_ratio:>10.2f}")
    print(f"🧮 期待值 (Exp): {expectancy:>10.2f} 點/筆")
    print("-" * 45)
    print(f"🏆 最終總淨利: {net_profit:>10.1f} 點")
    print(f"📉 最大回撤 (MDD): {mdd:>10.1f} 點")
    print(f"🚀 獲利比 (Profit/MDD): {abs(net_profit/mdd):>10.2f}")
    print("-" * 45)

    if expectancy < 10:
        print("⚠️ 警告：期待值過低，滑點與手續費可能吃掉所有利潤！")
    elif rr_ratio < 2:
        print("💡 建議：賺賠比較低，可以嘗試優化停損或移動停利。")
    else:
        print("🌟 診斷結論：這是一個強健的大趨勢策略。")

if __name__ == "__main__":
    run_deep_analysis()