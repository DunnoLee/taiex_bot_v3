from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine

def main():
    # 1. 準備零件 (Sim 版)
    # speed=0.5 方便你測試 telegram 互動
    feeder = CsvHistoryFeeder("data/history/TMF_History.csv", speed=0.1) 
    executor = MockExecutor(initial_capital=500000)
    
    # 2. 啟動引擎
    # 注意: 這裡用的 BotEngine 跟 Live 是同一個！
    bot = BotEngine(feeder, executor, symbol="TMF")
    
    # 3. 暖機 (其實 Sim 不需要，但呼叫也不會壞，保持一致性)
    # bot.load_warmup_data() 
    
    # 4. 出發
    bot.start()

if __name__ == "__main__":
    main()