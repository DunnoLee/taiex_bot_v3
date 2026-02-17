from modules.shioaji_feeder import ShioajiFeeder
from modules.mock_executor import MockExecutor # 暫時用Mock，未來換 RealExecutor
from core.engine import BotEngine

def main():
    # 1. 準備零件 (Live 版)
    feeder = ShioajiFeeder()
    executor = MockExecutor(initial_capital=1000000) # 實盤也可以先接 Mock 測試下單邏輯
    
    # 2. 啟動引擎
    bot = BotEngine(feeder, executor, symbol="TMF")
    
    # 3. 暖機 (兩邊通用！)
    bot.load_warmup_data()
    
    # 4. 出發
    bot.start()

if __name__ == "__main__":
    main()