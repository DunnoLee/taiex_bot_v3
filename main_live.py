import time
import sys
import os
import pandas as pd
from config.settings import Settings
from modules.shioaji_feeder import ShioajiFeeder
from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent
from core.loader import load_history_data

# --- 全域狀態 ---
system_running = True       # 程式是否執行中
auto_trading_active = True  # 是否允許自動交易 (可透過 /stop 暫停)

def main():
    global system_running, auto_trading_active
    print(f"🚀 TaiEx Bot V3.1 (Interactive Logic) 啟動...")
    print(f"==========================================")
    
    # 1. 初始化
    commander = TelegramCommander()
    feeder = ShioajiFeeder()
    strategy = MAStrategy() 
    
    # 🚀 使用共用模組載入歷史資料
    history_bars = load_history_data("data/history/TMF_History.csv", tail_count=3000)
    if history_bars:
        strategy.load_history_bars(history_bars)
        commander.send_message(f"✅ **暖機完成**\n載入 {len(history_bars)} 根 K 棒")
    else:
        print("⚠️ 無歷史資料，從 0 開始")

    # 2. 定義 Commander 的回呼函數
    
    def get_system_status():
        """/status: 回報系統健康度與開關狀態"""
        pos_text = "⚪️ 空手"
        if strategy.position > 0: pos_text = "🔴 多單持有"
        elif strategy.position < 0: pos_text = "🟢 空單持有"
        
        mode = "🟢 自動交易中" if auto_trading_active else "🟠 已暫停 (監控模式)"
        
        return (
            f"📊 **系統狀態**\n"
            f"------------------\n"
            f"⚙️ 模式: {mode}\n"
            f"🎯 標的: `{feeder.target_code}`\n"
            f"🧱 倉位: {pos_text} ({strategy.position})\n"
            f"📉 最新價: {strategy.raw_bars[-1]['close'] if strategy.raw_bars else 'Wait'}\n"
            f"------------------\n"
            f"MA({strategy.fast_window}/{strategy.slow_window})"
        )

    def get_balance():
        """/balance: 回報權益數"""
        # 未來: 這裡要呼叫 feeder.api.account_balance()
        # 目前: 先回報模擬狀態或提示
        try:
            # 嘗試抓取 Shioaji 的帳戶資訊 (如果有連線)
            # 注意: 這裡只是示範，實際欄位需參考 Shioaji 文件
            # acc_balance = feeder.api.account_balance() 
            return (
                f"💰 **帳戶權益概況**\n"
                f"------------------\n"
                f"⚠️ 實盤帳戶連接中 (尚未實作 RealExecutor)\n"
                f"------------------\n"
                f"目前策略虛擬倉位: {strategy.position} 口"
            )
        except Exception as e:
            return f"⚠️ 無法讀取餘額: {e}"

    def toggle_trading(enable: bool):
        """/start & /stop: 切換自動交易開關"""
        global auto_trading_active
        auto_trading_active = enable
        state = "啟動" if enable else "暫停"
        print(f"⚙️ [System] 自動交易已{state}")

    def shutdown_system():
        """/kill: 真的關閉程式"""
        global system_running
        
        # 1. 先優雅地道別
        print("\n💀 指揮官下達屠殺令 (Kill)，正在關閉系統...")
        commander.send_message("💀 **系統正在關機，指揮官晚安！ (Shutting down)**")
        
        # 2. 給一點時間讓訊息傳出去 (Telegram API 需要時間)
        time.sleep(1) 
        
        # 3. 執行關閉程序
        system_running = False
        feeder.stop()
        sys.exit(0)

    # 3. 綁定 callback
    commander.set_callbacks(
        status_cb=get_system_status,
        balance_cb=get_balance,
        toggle_cb=toggle_trading,
        shutdown_cb=shutdown_system
    )
    commander.start_listening()

    # 4. 連線
    try:
        feeder.connect()
        feeder.subscribe("TMF") 
        time.sleep(2)
        
        if not feeder.target_code:
            commander.send_message("❌ 無法取得合約代碼")
            sys.exit(1)
            
        aggregator = BarAggregator(symbol=feeder.target_code)
        
        # 發送啟動通知
        commander.send_startup_report(
            feeder.target_code, 
            f"MA({Settings.STRATEGY_MA_FAST}/{Settings.STRATEGY_MA_SLOW}) SL:{Settings.STOP_LOSS_POINT}"
        )
        
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        commander.send_message(f"❌ 系統崩潰: {e}")
        sys.exit(1)

    # 5. 資料流邏輯 (包含暫停開關)
    def on_strategy_signal(signal: SignalEvent):
        # 如果自動交易被暫停，就不動作 (也不發通知，或者發一個「訊號忽略」通知)
        if not auto_trading_active:
            print(f"🚫 [已暫停] 忽略訊號: {signal.signal_type}")
            return

        print(f"\n⚡️ [訊號] {signal.signal_type} | {signal.reason}")
        commander.send_signal_notification(signal)
        # TODO: RealExecutor.execute(signal)

    def on_bar_generated(bar: BarEvent):
        # 顯示進度
        print(f"📊 [Live] {bar.timestamp.strftime('%H:%M')} C:{bar.close} {'(Paused)' if not auto_trading_active else ''}", end='\r')
        
        # 即使暫停，我們還是要讓策略吃 K 棒 (更新 MA)，但不執行訊號
        # 這樣恢復時 MA 才是準的！
        signal = strategy.on_bar(bar)
        
        if signal:
            on_strategy_signal(signal)

    # 6. 綁定
    feeder.set_on_tick(aggregator.on_tick)
    aggregator.set_on_bar(on_bar_generated)

    print(f"✅ 系統就緒！監聽 {feeder.target_code}...")
    
    # 7. 主迴圈
    try:
        while system_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 手動中斷")
        commander.send_message("🛑 **系統已手動關閉**")
        feeder.stop()

if __name__ == "__main__":
    main()