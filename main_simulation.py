from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine
from modules.ma_strategy import MAStrategy
from config.settings import Settings
from modules.real_executor import RealExecutor

def main():
    my_strategy = MAStrategy(
        fast_window=30, 
        slow_window=240, 
        stop_loss=300.0,
        threshold=5.0,
        resample=5
    )
    print(f"🧠 [策略] 載入模組: {my_strategy.name}")

    # 1. 準備零件 (Sim 版)
    # speed=0.5 方便你測試 telegram 互動
    feeder = CsvHistoryFeeder("data/history/TMF_History.csv", speed=0.5) 
    executor = MockExecutor(initial_capital=500000)
    #executor = RealExecutor(api, dry_run=True)

    # 2. 啟動引擎
    # 注意: 這裡用的 BotEngine 跟 Live 是同一個！
    target_symbol = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
    bot = BotEngine(strategy=my_strategy, feeder=feeder, executor=executor, symbol=target_symbol)

    # 3. 暖機 (其實 Sim 不需要，但呼叫也不會壞，保持一致性)
    # bot.load_warmup_data() 
    
    # 4. 出發
    bot.start()

if __name__ == "__main__":
    main()