import itertools
import pandas as pd
import sys
import os
# 💡 導航修正：確保能找到 config 資料夾
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine
from core.recorder import TradeRecorder


def run_grid_search(strategy_class, param_grid: dict, history_file: str):
    """
    通用型網格搜索最佳化器 (Universal Grid Search Optimizer)
    """
    print(f"🔍 啟動最佳化引擎: 測試 {strategy_class.__name__} ...")
    
    # 1. 產生所有參數的排列組合
    keys = param_grid.keys()
    values = param_grid.values()
    combinations = list(itertools.product(*values))
    print(f"📊 總共需要測試 {len(combinations)} 組參數組合\n")

    results = []

    # 2. 開始馬拉松式回測
    for idx, combo in enumerate(combinations):
        # 將組合打包成字典 (例如 {'fast_window': 15, 'slow_window': 120})
        params = dict(zip(keys, combo))
        print(f"⏳ [{idx+1}/{len(combinations)}] 正在測試參數: {params} ...")
        
        # --- 初始化獨立的回測環境 ---
        # A. 實例化策略 (利用 **params 解包字典傳入參數)
        strategy = strategy_class(**params)
        
        # B. 獨立的 Executor (每次測試必須從 100 萬本金重新開始)
        executor = MockExecutor(initial_capital=1000000)
        
        # C. 獨立的 Feeder
        feeder = CsvHistoryFeeder(history_file, speed=0)
        
        # D. 啟動 Engine (關閉 Telegram 避免洗版)
        bot = BotEngine(strategy, feeder, executor, symbol="TMF", enable_telegram=False)
        
        # 為了避免幾萬行 Log 洗爆終端機，我們把 Recorder 指向 null (不存檔)
        # (這裡假設你不想要保留失敗組合的 CSV，只要看最終成績)
        bot.recorder = TradeRecorder() 
        bot.recorder.log_file = os.devnull #None # 如果你的系統允許 None 的話，或者指向一個暫存檔

        # --- 執行回測 ---
        bot.start()

        # --- 期末結算 (Mark-to-Market) ---
        bot.inject_flatten_signal(reason="期末結算")

        # --- 收集成績單 ---
        pnl = executor.total_pnl
        trades = len(executor.trades)
        win_rate = (executor.win_count / trades * 100) if trades > 0 else 0

        results.append({
            '參數組合': str(params),
            '總淨利': pnl,
            '交易次數': trades,
            '勝率(%)': round(win_rate, 2)
        })

    # 3. 整理並輸出排行榜
    df_results = pd.DataFrame(results)
    # 依據淨利由高到低排序
    df_results = df_results.sort_values(by='總淨利', ascending=False).reset_index(drop=True)
    
    print("\n" + "="*50)
    print(f"🏆 {strategy_class.__name__} 最佳化排行榜 (Top 5)")
    print("="*50)
    print(df_results.head(5).to_string(index=False))
    print("="*50 + "\n")

    return df_results

# ==========================================
# 🚀 執行區塊
# ==========================================
if __name__ == "__main__":
    from strategies.ma_adx_strategy import MaAdxStrategy
    from strategies.smart_hold_strategy import SmartHoldStrategy
    HISTORY_FILE = "data/history/TMF_History.csv"

    print("請選擇要最佳化的策略:")
    print("1: MA + ADX 趨勢狙擊策略")
    print("2: SmartHold 日線長抱策略")
    choice = input("輸入代碼 (1/2): ")

    if choice == '1':
        # 測試 MA-ADX 的參數
        param_grid = {
            'fast_window': [15, 30, 45],            # 測試 3 種快線
            'slow_window': [120, 240, 300],         # 測試 3 種慢線
            'adx_threshold': [20, 25, 30],          # 測試 3 種 ADX 門檻
            'adx_period': [14],                     #
            'resample': [5],                        # 固定 5分K
            'stop_loss': [250.0, 300.0, 400.0]      # 測試 3 種停損點
        }
        # 3 x 3 x 3 x 1 x 3 = 81 種組合
        run_grid_search(MaAdxStrategy, param_grid, HISTORY_FILE)

    elif choice == '2':
        # 測試 SmartHold 的參數
        param_grid = {
            'daily_ma_period': [10, 20, 60],        # 雙週線、月線、季線
            'threshold': [50.0, 100.0, 150.0],      # 避震器寬度
            'stop_loss': [600.0, 800.0, 1000.0]     # 大範圍停損
        }
        # 3 x 3 x 3 = 27 種組合
        run_grid_search(SmartHoldStrategy, param_grid, HISTORY_FILE)
    else:
        print("輸入錯誤，結束程式。")