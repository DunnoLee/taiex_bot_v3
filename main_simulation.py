import time
import sys
from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder  # <-- 用 CSV 假裝是 Shioaji
from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander
from modules.mock_executor import MockExecutor    # <-- 用 Mock 假裝成交
from core.event import BarEvent, SignalEvent

# --- 全域狀態 ---
system_running = True
auto_trading_active = True

# --- 設定 ---
DATA_FILE = "data/history/TMF_History.csv" # 確保你有這份檔案

def main():
    global system_running, auto_trading_active
    print(f"🎮 TaiEx Bot V3 (Simulation Mode) 啟動...")
    print(f"==========================================")
    
    # 1. 初始化
    commander = TelegramCommander()
    
    # ⚠️ 關鍵差異: 使用 CSV Feeder，但速度設慢一點 (speed=1.0 代表 1秒模擬1秒)
    # 如果你想快一點測試，可以設 speed=0.1 (10倍速)
    # 為了測試 Telegram 互動，建議設 speed=0.5 左右，才來得及打字
    feeder = CsvHistoryFeeder(DATA_FILE, speed=0.1) 
    
    strategy = MAStrategy()
    executor = MockExecutor(initial_capital=500000) # 模擬帳戶
    
    # 2. 定義 Commander 回呼 (跟 main_live 一模一樣)
    def get_system_status():
        pos_text = "⚪️ 空手"
        if strategy.position > 0: pos_text = "🔴 多單持有"
        elif strategy.position < 0: pos_text = "🟢 空單持有"
        mode = "🟢 自動交易" if auto_trading_active else "🟠 已暫停"
        
        # 顯示模擬帳戶損益
        pnl_text = f"${executor.total_pnl:,.0f}"
        
        return (
            f"🎮 **模擬演習狀態**\n"
            f"------------------\n"
            f"⚙️ 模式: {mode}\n"
            f"🧱 倉位: {pos_text}\n"
            f"💰 模擬損益: {pnl_text}\n"
            f"------------------\n"
            f"MA({strategy.fast_window}/{strategy.slow_window})"
        )

    def get_balance():
        return (
            f"💰 **模擬帳戶權益**\n"
            f"------------------\n"
            f"初始資金: ${executor.capital:,.0f}\n"
            f"累計損益: ${executor.total_pnl:,.0f}\n"
            f"交易次數: {len(executor.trades)}\n"
            f"勝率: {(executor.win_count/len(executor.trades)*100 if executor.trades else 0):.1f}%"
        )

    def toggle_trading(enable: bool):
        global auto_trading_active
        auto_trading_active = enable
        state = "啟動" if enable else "暫停"
        print(f"⚙️ [Sim] 自動交易已{state}")

    def shutdown_system():
        global system_running
        print("\n💀 演習結束，關閉系統...")
        commander.send_message("💀 **演習結束，系統關閉 (Simulation Ended)**")
        time.sleep(1)
        system_running = False
        feeder.stop() # 這會停止 Mock Feeder 的迴圈
        sys.exit(0)

    # 3. 綁定 Commander
    commander.set_callbacks(get_system_status, get_balance, toggle_trading, shutdown_system)
    commander.start_listening()

    # 4. 啟動 Mock Feeder
    feeder.connect()
    # Mock Feeder 不需要 subscribe，直接設定好 callback 即可

    # 5. 資料流邏輯
    def on_simulation_bar(bar: BarEvent):
        # 這是 MockFeeder 吐出來的歷史 K 棒
        # 我們假裝它是 Live Bar
        
        # 顯示進度
        status_icon = "▶️" if auto_trading_active else "⏸"
        print(f"📊 [Sim] {bar.timestamp} C:{bar.close:.0f} {status_icon}", end='\r')
        
        # 1. 餵給策略 (永遠不中斷，保持 MA 連續性)
        signal = strategy.on_bar(bar)
        
        # 2. 處理訊號
        if signal:
            if not auto_trading_active:
                print(f"\n🚫 [已暫停] 忽略訊號: {signal.signal_type}")
                return

            print(f"\n⚡️ [模擬訊號] {signal.signal_type} | {signal.reason}")
            
            # 3. 執行模擬下單
            trade_msg = executor.execute_signal(signal, bar.close)
            strategy.set_position(executor.current_position)
            
            # 4. 發送 Telegram 通知
            if trade_msg:
                commander.send_message(f"🎮 **模擬成交**\n{trade_msg}\n原因: {signal.reason}")

    # 6. 綁定
    feeder.set_on_bar(on_simulation_bar)
    
    # 發送啟動通知
    commander.send_startup_report("TMF_HISTORY (模擬)", "MA_30_240 (冠軍參數)")

    print(f"✅ 演習系統就緒！開始回放歷史資料...")
    
    # 7. 開始回放 (這會卡住 Main Thread，直到 CSV 跑完)
    try:
        feeder.start() 
        # 當 CSV 跑完後，feeder.start() 會結束
        print("\n🏁 歷史資料回放完畢")
        commander.send_message("🏁 **演習結束：歷史資料已播完**")
        executor.print_report()
        
    except KeyboardInterrupt:
        shutdown_system()

if __name__ == "__main__":
    main()