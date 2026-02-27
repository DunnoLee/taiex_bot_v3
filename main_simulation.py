from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine
from strategies.ma_strategy import MAStrategy
from config.settings import Settings
from modules.real_executor import RealExecutor
import time

import sys
def main():
    # my_strategy = MAStrategy(
    #     fast_window=30, 
    #     slow_window=240, 
    #     stop_loss=300.0,
    #     threshold=5.0,
    #     resample=5
    # )
    # from strategies.ma_adx_strategy import MaAdxStrategy
    # my_strategy = MaAdxStrategy()

    # from strategies.asym_ma_adx_strategy import AsymMaAdxStrategy
    # my_strategy = AsymMaAdxStrategy()
    from strategies.universal_ma_strategy import UniversalMaStrategy
    my_strategy = UniversalMaStrategy()
    # from strategies.smart_hold_strategy import SmartHoldStrategy
    # my_strategy = SmartHoldStrategy(daily_ma_period=20, stop_loss=800.0)

    print(f"🧠 [策略] 載入模組: {my_strategy.name}")

    # 1. 準備零件 (Sim 版)
    # speed=0.5 方便你測試 telegram 互動
    feeder = CsvHistoryFeeder("data/history/TMF_History.csv", speed=0.05) 
    executor = MockExecutor(initial_capital=500000)
    #executor = RealExecutor(api, dry_run=True)

    # 2. 啟動引擎
    # 注意: 這裡用的 BotEngine 跟 Live 是同一個！
    target_symbol = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
    bot = BotEngine(strategy=my_strategy, feeder=feeder, executor=executor, symbol=target_symbol)

    # =====================================================
    # 🛡️ 模擬核心防護：綁定「模擬券商」的成交回報 (與 Live 完全一致)
    # =====================================================
    def on_order_event(update_info, update_events):
        try:
            status_str = str(getattr(update_info, 'status', ''))
            
            if "Filled" in status_str or "Deal" in status_str:
                print(f"\n⚡️ [模擬回報] 偵測到模擬成交事件！啟動同步對帳機制...")
                
                # 🚀 啟動背景小工人，等帳本徹底結算完再對帳
                def _delayed_sync():
                    time.sleep(1.0) # 等待 1 秒確保 Executor 帳本更新完畢
                    
                    # 取得 Executor 目前算出來的真實部位
                    real_pos = executor.current_position
                    
                    # 強制更新策略大腦的影子帳本
                    bot.strategy.set_position(real_pos)
                    print(f"✅ [系統] 對帳完成！當前部位同步為: {real_pos}")
                    
                    # 順便發個 Telegram 通知
                    if hasattr(bot, 'commander') and bot.commander:
                        bot.commander.send_message(f"🔄 **模擬對帳完成**\n新倉位: {real_pos}")

                import threading
                threading.Thread(target=_delayed_sync, daemon=True).start()

        except Exception as e:
            print(f"⚠️ 處理模擬回報發生錯誤: {e}")

    # 把這個接線生綁定給我們的 MockExecutor
    executor.set_order_callback(on_order_event)
    # =====================================================

    # 3. 暖機 (其實 Sim 不需要，但呼叫也不會壞，保持一致性)
    # bot.load_warmup_data() 
    
    # 4. 出發
    # print("\n🟢 [系統] 模擬引擎啟動，按 Ctrl+C 停止...")
    # bot.start()
    # -----------------------------------------------------
    # 6. 正式開跑 (掛載全息投影儀表板)
    # -----------------------------------------------------
    print("\n🟢 [系統] 引擎啟動，準備切換至戰術儀表板...")
    time.sleep(2)

    # 1. 初始化 UI
    from modules.ui_dashboard import DashboardUI
    import threading
    ui = DashboardUI(bot)

    # 2. 🚀 把核心引擎「丟到背景」去跑 (這步最關鍵，不然會卡死！)
    bot_thread = threading.Thread(target=bot.start, daemon=True)
    bot_thread.start()

    # 3. 讓「主畫面」留給儀表板
    ui.start_ui(bot_thread)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 模擬結束")
        sys.exit(0)