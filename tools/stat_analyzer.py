import pandas as pd
import sys
import os

def analyze_log(log_path):
    print(f"📊 [Stat Analyzer] 正在分析: {log_path} ...")
    
    if not os.path.exists(log_path):
        print(f"❌ 找不到檔案: {log_path}")
        return

    try:
        # 1. 讀取 V3 格式的 Log
        df = pd.read_csv(log_path)
        
        # 2. 轉換格式
        df['Time'] = pd.to_datetime(df['Time'])
        df['Real_PnL'] = pd.to_numeric(df['Real_PnL'], errors='coerce').fillna(0)
        
        # 3. 過濾出有損益的交易 (Action 為平倉或反手時會產生 PnL)
        # 注意: V3 的 PnL 記錄在每一筆成交上，開倉通常是 0，平倉才有值
        trades = df[df['Real_PnL'] != 0].copy()
        
        if len(trades) == 0:
            print("⚠️ Log 中沒有發現已實現損益 (Real_PnL 全為 0)")
            return

        # 4. 計算統計數據
        total_pnl = trades['Real_PnL'].sum()
        win_trades = trades[trades['Real_PnL'] > 0]
        loss_trades = trades[trades['Real_PnL'] <= 0]
        
        win_count = len(win_trades)
        loss_count = len(loss_trades)
        total_count = len(trades)
        
        win_rate = (win_count / total_count * 100) if total_count > 0 else 0
        avg_win = win_trades['Real_PnL'].mean() if win_count > 0 else 0
        avg_loss = loss_trades['Real_PnL'].mean() if loss_count > 0 else 0
        pf = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # 5. 計算權益曲線與回撤 (Drawdown)
        df['Cumulative_PnL'] = df['Real_PnL'].cumsum()
        df['Peak'] = df['Cumulative_PnL'].cummax()
        df['Drawdown'] = df['Cumulative_PnL'] - df['Peak']
        max_dd = df['Drawdown'].min()

        # 6. 輸出報告
        print("\n" + "="*40)
        print("🏆 V3 策略績效報告")
        print("="*40)
        print(f"💰 總損益: ${total_pnl:,.0f} TWD")
        print(f"🔢 交易筆數: {total_count} 筆")
        print(f"📈 勝率: {win_rate:.2f}%")
        print(f"⚖️ 獲利因子 (PF): {pf:.2f}")
        print(f"💵 平均獲利: ${avg_win:,.0f}")
        print(f"💸 平均虧損: ${avg_loss:,.0f}")
        print(f"📉 最大回撤 (Max DD): ${max_dd:,.0f}")
        print("="*40 + "\n")

    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方式: python tools/stat_analyzer.py <log_file_path>")
        # 預設路徑 (方便你直接跑)
        default_path = "data/backtest_results/backtest_log.csv"
        if os.path.exists(default_path):
            analyze_log(default_path)
    else:
        analyze_log(sys.argv[1])