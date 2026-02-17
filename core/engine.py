import time
import sys
import threading
import datetime
from config.settings import Settings
from core.loader import load_history_data
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent, SignalType, EventType
from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander
from core.recorder import TradeRecorder

class BotEngine:
    """
    通用機器人引擎 (All-in-One Brain)
    負責協調 Feeder, Strategy, Executor 與 Telegram 之間的運作。
    """
    def __init__(self, feeder, executor, symbol="TMF", enable_telegram=True):
        self.feeder = feeder
        self.executor = executor
        self.symbol = symbol
        self.enable_telegram = enable_telegram

        # 1. 初始化核心組件
        self.commander = TelegramCommander()
        if not self.enable_telegram:
            # 強制關閉 Commander 的發送功能
            self.commander.enabled = False 
            print("🔕 [Engine] 靜音模式: Telegram 通知已關閉")
        # 讓策略讀取 Settings 的預設值 (MA30/240, SL300)
        self.strategy = MAStrategy()
        self.aggregator = BarAggregator(symbol)
        
        # 🆕 新增: 啟動黑盒子記錄器
        self.recorder = TradeRecorder()

        # 2. 全域狀態
        self.system_running = True
        self.auto_trading_active = True
        
        # 3. 綁定內部邏輯
        self._setup_callbacks()
        self._bind_events()

    def _setup_callbacks(self):
        """設定 Telegram 指令的回呼函數"""
        
        def get_status():
            pos_text = "⚪️ 空手"
            if self.strategy.position > 0: pos_text = f"🔴 多單 {self.strategy.position} 口"
            elif self.strategy.position < 0: pos_text = f"🟢 空單 {abs(self.strategy.position)} 口"
            
            mode = "🟢 自動交易中" if self.auto_trading_active else "🟠 已暫停 (監控模式)"
            
            # 取得最新價格 (從策略的快取中拿)
            last_price = "Wait"
            if self.strategy.raw_bars:
                last_price = int(self.strategy.raw_bars[-1]['close'])
            
            return (
                f"📊 **系統狀態報告**\n"
                f"------------------\n"
                f"⚙️ 模式: {mode}\n"
                f"🎯 標的: `{self.symbol}`\n"
                f"🧱 倉位: {pos_text}\n"
                f"💰 損益: ${self.executor.total_pnl:,.0f}\n"
                f"📉 最新價: {last_price}\n"
                f"------------------\n"
                f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) | SL:{self.strategy.stop_loss}"
            )

        def get_balance():
            # 回報 Executor 的資金狀態
            # 未來如果接 RealExecutor，這裡會呼叫 API 查詢真實權益數
            return (
                f"💰 **帳戶權益概況**\n"
                f"------------------\n"
                f"初始資金: ${self.executor.capital:,.0f}\n"
                f"目前權益: ${self.executor.capital + self.executor.total_pnl:,.0f}\n"
                f"累計損益: ${self.executor.total_pnl:,.0f}\n"
                f"勝率: {(self.executor.win_count / len(self.executor.trades) * 100) if self.executor.trades else 0:.1f}%"
            )

        def toggle_trading(enable: bool):
            self.auto_trading_active = enable
            state = "啟動" if enable else "暫停"
            print(f"⚙️ [Engine] 自動交易已{state}")

        def manual_trade(action: str, qty: int):
            """處理 /buy, /sell 指令 (含 Smart Close 邏輯)"""
            print(f"👋 [Manual] 收到手動交易指令: {action} {qty} 口")
            
            # 1. 取得當前大概價格 (用上一根 K 棒收盤價當作市價)
            current_price = 0
            current_time = datetime.datetime.now() # 預設為真實時間

            if self.strategy.raw_bars:
                last_bar = self.strategy.raw_bars[-1]
                current_price = last_bar['close']
                # 關鍵修正：使用 K 棒的時間，而不是電腦系統時間
                # 這樣 Log 才會跟模擬的 K 線圖對齊
                current_time = last_bar['datetime'] 
            else:
                self.commander.send_message("⚠️ 無法取得報價/時間，無法執行手動下單")
                return

            # ---------------------------------------------------------
            # 💡 修正：智慧判斷 (Smart Order Logic)
            # ---------------------------------------------------------
            current_pos = self.strategy.position
            target_signal = None
            
            # 邏輯: 如果指令方向與倉位相反，視為「平倉 (Flatten)」而不是「反手 (Reverse)」
            if action == "BUY":
                if current_pos < 0: # 手上有空單，買進是為了平倉
                    target_signal = SignalType.FLATTEN
                    print("💡 [Smart] 偵測到持有空單，將 /buy 轉換為平倉訊號")
                else:
                    target_signal = SignalType.LONG
            
            elif action == "SELL":
                if current_pos > 0: # 手上有多單，賣出是為了平倉
                    target_signal = SignalType.FLATTEN
                    print("💡 [Smart] 偵測到持有多單，將 /sell 轉換為平倉訊號")
                else:
                    target_signal = SignalType.SHORT

            # 2. 建立一個「人為」訊號
            #sig_type = SignalType.LONG if action == "BUY" else SignalType.SHORT
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=self.symbol,
                signal_type=target_signal,
                strength=1.0,
                reason=f"Manual {action} Command"
            )

            # -----------------------------------------------------
            # 💡 新增：捕捉 PnL 變動 (跟自動交易一樣)
            # -----------------------------------------------------
            pnl_before = self.executor.total_pnl


            # 3. 強制 Executor 執行 (不經過策略判斷)
            # 注意: 這裡假設 Executor 支援直接傳入 qty (如果 MockExecutor 沒支援，通常預設是 1)
            # 為了簡單起見，我們迴圈執行多次 (如果 qty > 1)
            msg = ""
            for _ in range(qty):
                # 這裡假設 execute_signal 已經處理了手續費和滑價
                res = self.executor.execute_signal(signal, current_price)
                if res: msg = res

            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before

            # 4. 重要！手動下單後，必須同步策略的倉位記憶
            self.strategy.set_position(self.executor.current_position)

            # 🚨 BUG FIX: 手動更新策略的入場價
            # 如果現在有倉位，就把入場價設為當前價格，避免下一秒被停損
            if self.strategy.position != 0:
                self.strategy.entry_price = current_price
            else:
                self.strategy.entry_price = 0.0

            # -----------------------------------------------------
            # 💡 新增：寫入 Log
            # -----------------------------------------------------
            # 我們把 Action 加上 "MANUAL_" 前綴，或者直接用 "BUY"/"SELL"
            # 為了讓 Visualizer 也能畫三角形，我們維持標準 Action 名稱
            # 但在 Message 裡註記是 Manual
            
            # 注意: 如果是平倉，executor 可能會回傳 "CLOSE_LONG" 之類的
            # 這裡簡單處理，直接記錄我們下的指令
            
            if msg: # 只有真的有成交才記
                self.recorder.write_trade(
                    timestamp=current_time,  # <--- 這裡改用模擬時間
                    symbol=self.symbol,
                    action=action, # "BUY" or "SELL"
                    price=current_price,
                    qty=qty,
                    strategy_name="Manual", # 策略名稱記為手動
                    pnl=realized_pnl,
                    msg=f"Telegram User Command ({action})"
                )

            self.commander.send_message(f"✅ **手動成交**\n{msg}\n修正後倉位: {self.strategy.position}")

        def sync_position():
            """處理 /sync 指令"""
            # 在實盤中，這裡要呼叫 shioaji API 查詢庫存
            # real_pos = self.feeder.api.get_position(self.symbol)
            
            # 目前模擬階段，我們假設「真實倉位」是 0 (或是你可以寫死一個數字測試)
            real_pos_simulated = 0 
            
            old_pos = self.strategy.position
            
            # 強制覆蓋
            self.strategy.set_position(real_pos_simulated)
            self.executor.current_position = real_pos_simulated
            
            return real_pos_simulated

        def flatten_position():
            """處理 /flat 指令：不論多空，全部清零"""
            current_pos = self.strategy.position
            
            if current_pos == 0:
                self.commander.send_message("⚪️ **目前已是空手 (Flat)，無需動作**")
                return

            print(f"👋 [Manual] 執行一鍵平倉，目前倉位: {current_pos}")

            # 1. 決定動作方向與口數
            # 如果是多單 (>0)，就要賣出 (SELL)
            # 如果是空單 (<0)，就要買進 (BUY)
            action = "SELL" if current_pos > 0 else "BUY"
            qty = abs(current_pos) # 絕對值，例如 -2 口就要買 2 口
            
            # 2. 取得環境資訊
            current_price = 0
            current_time = datetime.datetime.now()
            if self.strategy.raw_bars:
                last_bar = self.strategy.raw_bars[-1]
                current_price = last_bar['close']
                current_time = last_bar['datetime']

            # 3. 建立平倉訊號
            # 使用 FLATTEN 類型，明確告訴系統這是平倉
            sig_type = SignalType.FLATTEN 
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=self.symbol,
                signal_type=sig_type,
                strength=1.0,
                reason="Manual /flat Command"
            )

            # 4. 記錄 PnL
            pnl_before = self.executor.total_pnl

            # 5. 執行交易
            msg = ""
            # 因為我們要平掉 qty 口，所以執行 qty 次 (或是 executor 支援一次平倉)
            # 簡單起見，我們呼叫 executor
            res = self.executor.execute_signal(signal, current_price)
            if res: msg = res

            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before

            # 6. 同步狀態
            self.strategy.set_position(self.executor.current_position)
            self.strategy.entry_price = 0.0 # 平倉後成本歸零

            # 7. 寫 Log
            if msg:
                self.recorder.write_trade(
                    timestamp=current_time,
                    symbol=self.symbol,
                    action="FLATTEN", # 這裡記 FLATTEN 比較清楚
                    price=current_price,
                    qty=qty,
                    strategy_name="Manual",
                    pnl=realized_pnl,
                    msg="Telegram User Command (/flat)"
                )

            self.commander.send_message(f"✅ **已全數平倉**\n{msg}\n實現損益: ${realized_pnl:,.0f}\n目前倉位: {self.strategy.position}")

        def shutdown():
            print("\n💀 指揮官下達關機指令...")
            self.commander.send_message("💀 **系統正在關機 (System Shutdown)**")
            time.sleep(1)
            self.system_running = False
            self.feeder.stop()
            sys.exit(0)

        # 將上述函數綁定給 Commander
        self.commander.set_callbacks(
            status_cb=get_status,
            balance_cb=get_balance,
            toggle_cb=toggle_trading,
            shutdown_cb=shutdown,
            manual_trade_cb=manual_trade,
            sync_position_cb=sync_position,
            flatten_cb=flatten_position
        )

    def _bind_events(self):
        """綁定資料流: Feeder -> Aggregator -> Engine.on_bar"""
        self.feeder.set_on_tick(self.aggregator.on_tick)
        self.aggregator.set_on_bar(self.on_bar_generated)

    def load_warmup_data(self, csv_path="data/history/TMF_History.csv"):
        """預載歷史資料 (通用)"""
        history_bars = load_history_data(csv_path, tail_count=3000)
        if history_bars:
            self.strategy.load_history_bars(history_bars)
            self.commander.send_message(f"✅ **暖機完成**\n已載入 {len(history_bars)} 根歷史 K 棒")
        else:
            print("⚠️ 無歷史資料，策略將從 0 開始累積")

    def on_bar_generated(self, bar: BarEvent):
        """核心運算迴圈: 每分鐘 K 棒產生時觸發"""
        # 顯示終端機進度
        icon = "▶️" if self.auto_trading_active else "⏸"
        print(f"📊 {bar.timestamp.strftime('%H:%M')} C:{int(bar.close)} {icon}", end='\r')
        
        # 1. 餵給策略 (無論是否暫停，都要維持 MA 計算)
        signal = self.strategy.on_bar(bar)
        
        # 2. 處理訊號
        if signal:
            # 如果暫停交易，則忽略訊號
            if not self.auto_trading_active:
                print(f"\n🚫 [已暫停] 忽略訊號: {signal.signal_type}")
                return

            print(f"\n⚡️ [訊號觸發] {signal.signal_type} | {signal.reason}")
            
            # 1. 紀錄交易前的總損益
            pnl_before = self.executor.total_pnl

            # 3. 執行交易
            trade_msg = self.executor.execute_signal(signal, bar.close)
            
            # 3. 計算這一筆的「已實現損益」 (交易後 - 交易前)
            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before

            # 4. 同步倉位狀態 (讓策略知道現在手上有單)
            self.strategy.set_position(self.executor.current_position)
            
            # 5. 發送通知
            if trade_msg:
                # 解析動作 (LONG/SHORT)
                #action = "BUY" if signal.signal_type in ["LONG", "FLATTEN_LONG"] else "SELL"
                action = signal.signal_type.name # LONG, SHORT...
                # 簡單計算 PnL (如果是平倉才有 PnL，開倉通常是 0)
                # 注意: 這裡的 PnL 最好是由 executor 回傳，我們這邊簡化處理
                # 如果你想精準記錄 PnL，建議讓 Executor 回傳詳細 dict 而不是字串 msg
                
                # 如果是停損，通常 Signal Reason 會寫，我們把它記下來
                # 這樣 visualizer 才能畫叉叉

                self.recorder.write_trade(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    #action=signal.signal_type.name, # LONG, SHORT, FLATTEN
                    action=action,
                    price=bar.close,
                    qty=1, # 暫定 1 口
                    strategy_name=self.strategy.name,
                    pnl=realized_pnl,  # <--- 這裡不再是 0 了！
                    msg=signal.reason
                )
                self.commander.send_message(f"⚡️ **自動成交**\n{trade_msg}\n原因: {signal.reason}")

    def start(self):
        """啟動引擎"""
        print(f"🚀 Engine Started: {self.symbol}")
        self.commander.start_listening()
        self.commander.send_startup_report(
            self.symbol, 
            f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) SL:{self.strategy.stop_loss}"
        )
        
        try:
            self.feeder.connect()
            
            # 如果是 Shioaji Feeder，需要訂閱
            if hasattr(self.feeder, 'subscribe'):
                self.feeder.subscribe(self.symbol)
            
            self.feeder.start()
            
            # 保持主程式運作 (針對 Live 模式)
            # 如果是 Sim 模式，feeder.start() 本身就會卡住直到跑完，所以這裡不會執行到
            while self.system_running:
                time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n🛑 手動中斷")
            self.commander.send_message("🛑 **系統已手動中斷**")
            self.feeder.stop()