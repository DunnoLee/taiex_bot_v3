import os
import shutil
from datetime import datetime
from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine
from core.recorder import TradeRecorder
from modules.ma_strategy import MAStrategy

# --- 設定 ---
HISTORY_FILE = "data/history/TMF_History.csv"
BACKTEST_DIR = "data/backtest_results"

def main():
    print(f"📉 TaiEx Bot V3 (Backtest Mode) 啟動...")
    print(f"==========================================")
    
    my_strategy = MAStrategy(
        fast_window=30, 
        slow_window=240, 
        stop_loss=300.0,
        threshold=5.0,
        resample=5
    )
    print(f"🧠 [策略] 載入模組: {my_strategy.name}")

    # 1. 準備環境
    # 為了避免跟實盤的 Log 混在一起，我們把回測結果放在獨立資料夾
    if not os.path.exists(BACKTEST_DIR):
        os.makedirs(BACKTEST_DIR)
        
    # 2. 初始化組件
    # speed=0 代表全速運轉 (不等待)
    feeder = CsvHistoryFeeder(HISTORY_FILE, speed=0) 
    executor = MockExecutor(initial_capital=1000000)
    
    # 3. 啟動引擎 (關鍵：enable_telegram=False)
    bot = BotEngine(my_strategy,feeder, executor, symbol="TMF", enable_telegram=False)
    
    # 4. 強制覆寫 Engine 的 Recorder 路徑 (為了把 Log 存到 backtest 資料夾)
    # 這樣你的 Visualizer 比較好找
    log_file_path = os.path.join(BACKTEST_DIR, "backtest_log.csv")
    bot.recorder.log_file = log_file_path
    
    # 重寫 Header
    import csv
    with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 欄位必須跟 visualizer 吃的一樣
        writer.writerow(["Time", "Symbol", "Action", "Price", "Qty", "Strategy", "Real_PnL", "Message"])
    
    print(f"🚀 開始極速回測 (來源: {HISTORY_FILE})...")
    
    # 5. 執行 (因為 speed=0，這裡會瞬間跑完)
    bot.start()
    
    # 6. 顯示結果
    print("\n" + "="*40)
    print(f"🏁 回測結束")
    print(f"💰 最終損益: ${executor.total_pnl:,.0f}")
    print(f"🔢 交易次數: {len(executor.trades)}")
    print(f"🏆 勝率: {(executor.win_count / len(executor.trades) * 100) if executor.trades else 0:.1f}%")
    print(f"📂 詳細 Log 已儲存至: {log_file_path}")
    print("="*40)
    
    print("\n💡 提示: 現在你可以執行 Visualizer 了:")
    print(f"   python tools/visualizer.py {log_file_path}")

if __name__ == "__main__":
    main()