import sys
import os
from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder
from modules.ma_strategy import MAStrategy
from modules.mock_executor import MockExecutor # 引入我們剛寫的執行器
from core.event import BarEvent

# --- 設定 ---
BIG_DATA_PATH = "data/history/TMF_History.csv"
SAMPLE_DATA_PATH = "data_sample.csv"
target_file = BIG_DATA_PATH if os.path.exists(BIG_DATA_PATH) else SAMPLE_DATA_PATH

def main():
    print(f"🚀 TaiEx Bot V3 (Mock Replay Mode) 啟動...")
    print(f"📂 資料來源: {target_file}")
    
    # 1. 初始化元件
    strategy = MAStrategy() 
    feeder = CsvHistoryFeeder(target_file, speed=0.0) # 全速運轉
    executor = MockExecutor(initial_capital=30000)    # 你的保證金 3萬
    
    print(f"🧠 策略: MA ({strategy.fast_window}/{strategy.slow_window})")
    print(f"⏳ 正在回放歷史數據，請稍候... (不印出詳細 Log 以加速)")

    # 2. 定義處理流程 (這就是 Event Engine 的雛形)
    def process_event(event: BarEvent):
        # A. 策略運算
        signal = strategy.on_bar(event)
        
        # B. 執行交易
        if signal:
            # 呼叫執行器，並傳入當前價格 (模擬成交用)
            result_msg = executor.execute_signal(signal, event.close)
            
            # C. 同步策略倉位 (這點很重要！策略必須知道自己成交了沒)
            # 在 Mock 模式下，我們假設一定成交
            strategy.set_position(executor.current_position)
            
            # 只印出有交易的時刻
            if result_msg:
                print(f"[{event.timestamp}] {result_msg}")

    # 3. 連線並綁定
    feeder.connect()
    feeder.set_on_bar(process_event)
    
    # 4. 開始執行
    try:
        feeder.start()
        
        # 5. 結束後印出報告
        executor.print_report()
        
    except KeyboardInterrupt:
        print("\n🛑 使用者中斷")
        executor.print_report()

if __name__ == "__main__":
    main()