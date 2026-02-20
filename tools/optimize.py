import sys
import time
import pandas as pd
from itertools import product
from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder
from strategies.ma_strategy import MAStrategy
from modules.mock_executor import MockExecutor
from core.event import BarEvent

# --- 設定 ---
DATA_FILE = "data/history/TMF_History.csv" # 請確保路徑正確
OUTPUT_FILE = "optimization_results.csv"

# 定義我們要搜尋的參數範圍 (Parameter Space)
# 這是一個排列組合： 5 * 5 * 3 = 75 種組合 (你可以自己加多)
param_grid = {
    "fast_window": [30],
    "slow_window": [240],
    "threshold": [5.0],
    "resample": [5], # 固定用 5分K，或者你也可以測 [5, 10, 15]

    # 新增測試項目：止損要設多少最賺？
    "stop_loss": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 1000.0]
}

def run_backtest(params):
    """執行單次回測"""
    # 1. 初始化
    strategy = MAStrategy(
        fast_window=params['fast_window'],
        slow_window=params['slow_window'],
        threshold=params['threshold'],
        resample=params['resample'],
        stop_loss=params['stop_loss']  # <--- 關鍵修改
    )
    strategy.silent_mode = True # 閉嘴模式
    
    executor = MockExecutor(initial_capital=500000)
    feeder = CsvHistoryFeeder(DATA_FILE, speed=0.0) # 全速
    
    # 2. 綁定流程 (簡化版 Main Loop)
    def process_event(event: BarEvent):
        signal = strategy.on_bar(event)
        if signal:
            msg = executor.execute_signal(signal, event.close)
            strategy.set_position(executor.current_position)

    feeder.connect()
    feeder.set_on_bar(process_event)
    feeder.start()
    
    # 3. 回傳結果
    total_trades = len(executor.trades)
    win_rate = (executor.win_count / total_trades * 100) if total_trades > 0 else 0
    
    return {
        **params, # 把參數也記下來
        "Total_PnL": executor.total_pnl,
        "Trades": total_trades,
        "Win_Rate": round(win_rate, 2),
        "Max_DD": "N/A" # 暫時沒算最大回撤，之後可加
    }

def main():
    print(f"🚀 開始參數最佳化 (來源: {DATA_FILE})")
    
    # 產生所有參數組合
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in product(*values)]
    
    # 過濾掉不合理的組合 (例如 快線 >= 慢線)
    valid_combinations = [
        c for c in combinations 
        if c['fast_window'] < c['slow_window']
    ]
    
    print(f"🔍 總共要測試 {len(valid_combinations)} 組參數...")
    print(f"☕️ 這可能需要一點時間，去泡杯咖啡吧...")
    
    results = []
    start_time = time.time()

    for i, params in enumerate(valid_combinations):
        # 顯示進度條
        print(f"[{i+1}/{len(valid_combinations)}] Testing: {params} ... ", end="", flush=True)
        
        try:
            res = run_backtest(params)
            results.append(res)
            print(f"PnL: ${res['Total_PnL']:,.0f}")
        except Exception as e:
            print(f"Error: {e}")

    # 轉成 DataFrame 並排序
    df = pd.DataFrame(results)
    df = df.sort_values(by="Total_PnL", ascending=False) # 賺最多的排前面
    
    print("\n" + "="*50)
    print("🏆 最佳參數 TOP 5")
    print("="*50)
    print(df.head(5).to_string(index=False))
    
    # 存檔
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ 詳細報告已儲存至: {OUTPUT_FILE}")
    print(f"⏱ 總耗時: {time.time() - start_time:.1f} 秒")

if __name__ == "__main__":
    main()