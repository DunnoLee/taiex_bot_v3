import time
import sys
from config.settings import Settings
from core.loader import load_history_data
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent
from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander

class BotEngine:
    """
    通用機器人引擎
    核心邏輯: Feeder -> Aggregator -> Strategy -> Executor -> Telegram
    """
    def __init__(self, feeder, executor, symbol="TMF"):
        self.feeder = feeder
        self.executor = executor
        self.symbol = symbol
        
        # 1. 初始化核心組件
        self.commander = TelegramCommander()
        self.strategy = MAStrategy()
        self.aggregator = BarAggregator(symbol)
        
        # 2. 全域狀態
        self.system_running = True
        self.auto_trading_active = True
        
        # 3. 綁定內部邏輯
        self._setup_callbacks()
        self._bind_events()

    def _setup_callbacks(self):
        """設定 Telegram 指令的回呼函數 (只寫一次，兩邊通用！)"""
        
        def get_status():
            pos_text = "⚪️ 空手"
            if self.strategy.position > 0: pos_text = "🔴 多單持有"
            elif self.strategy.position < 0: pos_text = "🟢 空單持有"
            
            mode = "🟢 自動交易" if self.auto_trading_active else "🟠 已暫停"
            price = self.strategy.raw_bars[-1]['close'] if self.strategy.raw_bars else 'N/A'
            
            return (
                f"📊 **系統狀態**\n"
                f"------------------\n"
                f"⚙️ 模式: {mode}\n"
                f"🎯 標的: `{self.symbol}`\n"
                f"🧱 倉位: {pos_text} ({self.strategy.position})\n"
                f"💰 損益: ${self.executor.total_pnl:,.0f} (模擬/實盤)\n"
                f"📉 最新價: {price}\n"
                f"------------------\n"
                f"MA({self.strategy.fast_window}/{self.strategy.slow_window})"
            )

        def get_balance():
            # 這裡呼叫 Executor 的查詢功能
            return f"💰 **權益數**: ${self.executor.capital:,.0f}"

        def toggle_trading(enable: bool):
            self.auto_trading_active = enable
            state = "啟動" if enable else "暫停"
            print(f"⚙️ [Engine] 自動交易已{state}")

        def manual_trade(action: str, qty: int):
            """處理 /buy, /sell"""
            print(f"👋 [Manual] 手動交易: {action} {qty}")
            # 建立一個假訊號來觸發下單流程
            # 注意: 這裡直接操作 executor 比較快
            if action == "BUY":
                msg = self.executor.execute_signal(SignalEvent(self.symbol, "LONG", 1.0, "Manual Buy"), 0) # 0 價格代表市價
                self.strategy.position += qty # 簡單修正
            elif action == "SELL":
                msg = self.executor.execute_signal(SignalEvent(self.symbol, "SHORT", 1.0, "Manual Sell"), 0)
                self.strategy.position -= qty
            
            self.commander.send_message(f"✅ 手動成交: {action} {qty} 口")

        def sync_position():
            """處理 /sync"""
            real_pos = 0 # 未來這裡呼叫 feeder.api.get_position
            old_pos = self.strategy.position
            self.strategy.set_position(real_pos)
            self.executor.current_position = real_pos # 同步 Executor
            return real_pos

        def shutdown():
            print("\n💀 系統關閉中...")
            self.commander.send_message("💀 **系統關機 (Shutdown)**")
            time.sleep(1)
            self.system_running = False
            self.feeder.stop()
            sys.exit(0)

        # 綁定給 Commander
        self.commander.set_callbacks(
            status_cb=get_status,
            balance_cb=get_balance,
            toggle_cb=toggle_trading,
            shutdown_cb=shutdown,
            manual_trade_cb=manual_trade,
            sync_position_cb=sync_position
        )

    def _bind_events(self):
        """綁定資料流"""
        # Feeder -> Aggregator
        self.feeder.set_on_tick(self.aggregator.on_tick)
        
        # Aggregator -> On Bar
        self.aggregator.set_on_bar(self.on_bar_generated)

    def load_warmup_data(self, csv_path="data/history/TMF_History.csv"):
        """預載歷史資料"""
        history_bars = load_history_data(csv_path, tail_count=3000)
        if history_bars:
            self.strategy.load_history_bars(history_bars)
            self.commander.send_message(f"✅ **暖機完成**\n載入 {len(history_bars)} 根 K 棒")
        else:
            print("⚠️ 無歷史資料，從 0 開始")

    def on_bar_generated(self, bar: BarEvent):
        # 顯示進度
        icon = "▶️" if self.auto_trading_active else "⏸"
        print(f"📊 {bar.timestamp} C:{bar.close:.0f} {icon}", end='\r')
        
        # 1. 策略運算 (永遠執行)
        signal = self.strategy.on_bar(bar)
        
        # 2. 訊號處理
        if signal:
            if not self.auto_trading_active:
                print(f"\n🚫 [已暫停] 忽略訊號: {signal.signal_type}")
                return

            print(f"\n⚡️ [訊號] {signal.signal_type} | {signal.reason}")
            
            # 3. 執行交易
            trade_msg = self.executor.execute_signal(signal, bar.close)
            
            # 4. 更新策略倉位
            self.strategy.set_position(self.executor.current_position)
            
            # 5. 通知
            if trade_msg:
                self.commander.send_message(f"⚡️ **成交回報**\n{trade_msg}\n原因: {signal.reason}")

    def start(self):
        """啟動引擎"""
        print(f"🚀 Engine Start: {self.symbol}")
        self.commander.start_listening()
        self.commander.send_startup_report(self.symbol, "MA(30/240)")
        
        try:
            self.feeder.connect() # Live會連線，Sim會準備
            if hasattr(self.feeder, 'subscribe'):
                 self.feeder.subscribe(self.symbol)
            
            self.feeder.start() # 開始迴圈
            
            # 對於 Live 模式，這裡需要一個無窮迴圈
            # 對於 Sim 模式，start() 自己就是迴圈，跑完就結束
            if not isinstance(self.feeder.start, type(lambda:0)): # 簡單判斷是否為 blocking
                 while self.system_running:
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            self.commander.send_message("🛑 **手動中斷**")
            self.feeder.stop()