import time
import sys
import datetime
from config.settings import Settings
from core.loader import load_history_data
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent, SignalType, EventType
#from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander
from core.recorder import TradeRecorder
import pandas as pd

class BotEngine:
    """
    通用機器人引擎 (All-in-One Brain) - V3.8 真實回報版
    修正: /balance 與 /status 會依據 Executor 類型，
    自動切換顯示「真實 API 數據」或「模擬帳本數據」。
    """
    def __init__(self, strategy, feeder, executor, symbol="TMF", enable_telegram=True):
        self.strategy = strategy
        self.feeder = feeder
        self.executor = executor
        self.symbol = symbol
        self.enable_telegram = enable_telegram
        
        # 1. 初始化核心組件
        self.commander = TelegramCommander()
        if not self.enable_telegram:
            self.commander.enabled = False
            
        #self.strategy = MAStrategy()
        self.aggregator = BarAggregator(symbol)
        self.recorder = TradeRecorder()
        
        # 2. 全域狀態
        self.system_running = True
        self.auto_trading_active = True
        
        # 3. 綁定內部邏輯
        self._setup_callbacks()
        self._bind_events()

    def _setup_callbacks(self):
        """設定 Telegram 指令的回呼函數"""
        
        # --- 輔助函數: 判斷當前模式 ---
        def get_mode_info():
            # 檢查 Executor 類型
            is_real = hasattr(self.executor, 'api') # RealExecutor 才有 api 屬性
            is_dry = getattr(self.executor, 'dry_run', False)
            
            if not is_real:
                return "🎮 模擬回測 (Simulation)", False
            elif is_dry:
                return "🛡️ 演習模式 (Dry Run)", True
            else:
                return "🔥 真槍實彈 (Live Trading)", True

        def get_status():
            mode_str, is_real = get_mode_info()
            
            # 1. 取得策略視角狀態 (Shadow)
            pos_text = "⚪️ 空手"
            if self.strategy.position > 0: pos_text = f"🔴 多單 {self.strategy.position} 口"
            elif self.strategy.position < 0: pos_text = f"🟢 空單 {abs(self.strategy.position)} 口"
            
            run_state = "🟢 運轉中" if self.auto_trading_active else "🟠 已暫停"
            
            # 最新價
            last_price = "Wait"
            if self.strategy.raw_bars:
                last_price = int(self.strategy.raw_bars[-1]['close'])
            
            report = (
                f"📊 **系統狀態報告**\n"
                f"------------------\n"
                f"⚙️ 模式: {mode_str}\n"
                f"🚦 狀態: {run_state}\n"
                f"🎯 標的: `{self.symbol}` @ {last_price}\n"
                f"🤖 **策略倉位**: {pos_text}\n"
            )

            # 2. 如果是實戰，追加 API 真實數據
            if is_real:
                try:
                    real_pos = self.executor.get_position()
                    real_pos_text = "⚪️ 0"
                    if real_pos > 0: real_pos_text = f"🔴 +{real_pos}"
                    elif real_pos < 0: real_pos_text = f"🟢 {real_pos}"
                    
                    report += f"🏦 **券商持倉**: {real_pos_text} (Real)\n"
                    
                    # 警示：如果策略跟券商不同步
                    if real_pos != self.strategy.position:
                        report += "⚠️ **警告**: 倉位不同步！請用 /sync 修正\n"
                        
                except Exception as e:
                    report += f"❌ API 查詢失敗: {e}\n"

            report += f"------------------\n"
            report += f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) | SL:{self.strategy.stop_loss}"
            return report

        def get_balance():
            mode_str, is_real = get_mode_info()
            
            # 1. 影子帳本數據 (模擬/回測用)
            shadow_equity = self.executor.capital + self.executor.total_pnl
            shadow_pnl = self.executor.total_pnl
            
            report = f"💰 **帳戶權益概況**\n"
            report += f"模式: {mode_str}\n"
            report += f"------------------\n"

            # 2. 如果是實戰，優先顯示 API 數據
            if is_real:
                try:
                    real_equity = self.executor.get_balance() # 呼叫 RealExecutor 的 API 查詢
                    report += f"🏦 **券商權益**: ${real_equity:,}\n"
                    
                    # 簡單計算今日概略損益 (假設初始資金是啟動時的權益，這裡比較難算準，先不顯示)
                    # 或者顯示 API 回傳的未實現損益? (目前 RealExecutor 沒實作 query pnl，先跳過)
                    
                    report += f"------------------\n"
                except Exception as e:
                    report += f"❌ 券商資料讀取失敗: {e}\n"

            # 3. 顯示機器人內部的績效 (參考用)
            report += f"🤖 **策略權益**: ${shadow_equity:,.0f} (Shadow)\n"
            report += f"📊 **策略損益**: ${shadow_pnl:,.0f}\n"
            
            trades_count = len(self.executor.trades)
            win_rate = (self.executor.win_count / trades_count * 100) if trades_count > 0 else 0
            report += f"🏆 **策略勝率**: {win_rate:.1f}% ({trades_count} trades)"
            
            return report

        def toggle_trading(enable: bool):
            self.auto_trading_active = enable
            state = "啟動" if enable else "暫停"
            print(f"⚙️ [Engine] 自動交易已{state}")

        def manual_trade(action: str, qty: int):
            """處理 /buy, /sell 指令 (含 Smart Close 邏輯)"""
            print(f"👋 [Manual] 收到手動交易指令: {action} {qty} 口")
            
            current_price = 0
            current_time = datetime.datetime.now()
            if self.strategy.raw_bars:
                last_bar = self.strategy.raw_bars[-1]
                current_price = last_bar['close']
                current_time = last_bar['datetime']
            
            # 智慧判斷
            current_pos = self.strategy.position
            target_signal = None
            
            if action == "BUY":
                if current_pos < 0:
                    target_signal = SignalType.FLATTEN
                    print("💡 [Smart] 偵測到持有空單，將 /buy 轉換為平倉訊號")
                else:
                    target_signal = SignalType.LONG
            elif action == "SELL":
                if current_pos > 0:
                    target_signal = SignalType.FLATTEN
                    print("💡 [Smart] 偵測到持有多單，將 /sell 轉換為平倉訊號")
                else:
                    target_signal = SignalType.SHORT

            signal = SignalEvent(EventType.SIGNAL, self.symbol, target_signal, 1.0, f"Manual {action}")

            pnl_before = self.executor.total_pnl
            
            msg = ""
            # 呼叫 Executor (Mock 或 Real)
            # 注意: RealExecutor 會根據 dry_run 決定是否真下單
            # 但這裡的 msg 會回傳 "委託成功 ID..."
            for _ in range(qty):
                res = self.executor.execute_signal(signal, current_price)
                if res: msg = res

            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before
            
            # 更新策略倉位
            self.strategy.set_position(self.executor.current_position)
            
            # 更新成本價
            if self.strategy.position != 0:
                self.strategy.entry_price = current_price 
            else:
                self.strategy.entry_price = 0.0

            # 寫 Log
            if msg: 
                self.recorder.write_trade(
                    timestamp=current_time,
                    symbol=self.symbol,
                    action=action,
                    price=current_price,
                    qty=qty,
                    strategy_name="Manual",
                    pnl=realized_pnl,
                    msg=f"Telegram User Command ({action})"
                )

            self.commander.send_message(f"✅ **手動成交**\n{msg}\n修正後倉位: {self.strategy.position}")

        def flatten_position():
            """處理 /flat 指令"""
            current_pos = self.strategy.position
            if current_pos == 0:
                self.commander.send_message("⚪️ **目前已是空手 (Flat)，無需動作**")
                return

            print(f"👋 [Manual] 執行一鍵平倉，目前倉位: {current_pos}")
            
            current_price = 0
            current_time = datetime.datetime.now()
            if self.strategy.raw_bars:
                last_bar = self.strategy.raw_bars[-1]
                current_price = last_bar['close']
                current_time = last_bar['datetime']

            sig_type = SignalType.FLATTEN 
            signal = SignalEvent(EventType.SIGNAL, self.symbol, sig_type, 1.0, "Manual /flat")

            pnl_before = self.executor.total_pnl
            
            msg = ""
            res = self.executor.execute_signal(signal, current_price)
            if res: msg = res

            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before

            self.strategy.set_position(self.executor.current_position)
            self.strategy.entry_price = 0.0

            if msg:
                self.recorder.write_trade(
                    timestamp=current_time,
                    symbol=self.symbol,
                    action="FLATTEN",
                    price=current_price,
                    qty=abs(current_pos),
                    strategy_name="Manual",
                    pnl=realized_pnl,
                    msg="Telegram User Command (/flat)"
                )

            self.commander.send_message(f"✅ **已全數平倉**\n{msg}\n實現損益: ${realized_pnl:,.0f}\n目前倉位: {self.strategy.position}")

        def sync_position():
            """處理 /sync 指令 (強制同步真實倉位)"""
            mode_str, is_real = get_mode_info()
            
            if not is_real:
                self.commander.send_message("⚠️ 模擬模式下無法同步真實倉位，將重置為 0。")
                real_pos = 0
            else:
                try:
                    self.commander.send_message("🔄 正在向券商查詢真實持倉...")
                    real_pos = self.executor.get_position()
                except Exception as e:
                    self.commander.send_message(f"❌ 同步失敗: {e}")
                    return

            old_pos = self.strategy.position
            
            # 強制覆蓋 Engine 和 Executor 的影子帳本
            self.strategy.set_position(real_pos)
            self.executor.current_position = real_pos
            
            # 歸零均價 (因為我們不知道真實成本)
            # 或者未來可以透過 api.list_positions 抓真實成本價
            self.executor.avg_price = 0.0 
            
            self.commander.send_message(
                f"✅ **同步完成**\n"
                f"------------------\n"
                f"舊倉位: {old_pos}\n"
                f"新倉位: {real_pos} (以券商為準)\n"
                f"模式: {mode_str}"
            )
            return real_pos

        def shutdown():
            print("\n💀 指揮官下達關機指令...")
            self.commander.send_message("💀 **系統正在關機 (System Shutdown)**")
            time.sleep(1)
            self.system_running = False
            self.feeder.stop()
            sys.exit(0)

        # 綁定 Callback
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
        """綁定事件流 (Data Pipeline)"""
        
        # 情境 A: Feeder 是餵 Tick 的 (如 ShioajiFeeder)
        if hasattr(self.feeder, 'set_on_tick'):
            self.feeder.set_on_tick(self.aggregator.on_tick)
        
        # 情境 B: Feeder 是餵 Bar 的 (如 MockFeeder)
        # 我們直接把 Engine 的 on_bar_generated 綁給它
        if hasattr(self.feeder, 'set_on_bar'):
            self.feeder.set_on_bar(self.on_bar_generated)
            
        # Aggregator 產生的 Bar 也要綁定
        self.aggregator.set_on_bar(self.on_bar_generated)

    def load_warmup_data(self, csv_path="data/history/TMF_History.csv"):
        history_bars = load_history_data(csv_path, tail_count=3000)
        if history_bars:
            self.strategy.load_history_bars(history_bars)
            self.commander.send_message(f"✅ **暖機完成**\n已載入 {len(history_bars)} 根歷史 K 棒")
        else:
            print("⚠️ 無歷史資料，策略將從 0 開始累積")

    def on_bar_generated(self, bar: BarEvent):
        icon = "▶️" if self.auto_trading_active else "⏸"
        print(f"📊 {bar.timestamp.strftime('%H:%M')} C:{int(bar.close)} {icon}", end='\r')
        
        signal = self.strategy.on_bar(bar)
        
        if signal:
            if not self.auto_trading_active:
                print(f"\n🚫 [已暫停] 忽略訊號: {signal.signal_type}")
                return

            print(f"\n⚡️ [訊號觸發] {signal.signal_type} | {signal.reason}")
            
            pnl_before = self.executor.total_pnl
            trade_msg = self.executor.execute_signal(signal, bar.close)
            pnl_after = self.executor.total_pnl
            realized_pnl = pnl_after - pnl_before
            
            self.strategy.set_position(self.executor.current_position)
            
            if trade_msg:
                action = signal.signal_type.name
                self.recorder.write_trade(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    action=action,
                    price=bar.close,
                    qty=1,
                    strategy_name=self.strategy.name,
                    pnl=realized_pnl,
                    msg=signal.reason
                )
                self.commander.send_message(f"⚡️ **自動成交**\n{trade_msg}\n原因: {signal.reason}")

    def sync_warmup_data_from_api(self):
        """
        [雙軌數據核心]
        檢查策略目前的資料進度，並從 API 抓取缺少的「溫數據 (Warm Data)」。
        """
        # 1. 只有 ShioajiFeeder 才有能力抓 API，MockFeeder 做不到
        if not hasattr(self.feeder, 'fetch_kbars'):
            print("⚠️ [Engine]目前的 Feeder 不支援 API 回補，跳過。")
            return

        # 2. 決定要從哪一天開始抓
        start_date = datetime.datetime.now().strftime("%Y-%m-%d") # 預設抓今天
        
        # 如果策略已經有載入 CSV 歷史資料，我們就從「最後一筆資料的日期」開始抓
        if self.strategy.raw_bars:
            last_bar = self.strategy.raw_bars[-1]
            
            # 判斷是 dict 還是物件 (相容性處理)
            if isinstance(last_bar, dict):
                last_dt = pd.to_datetime(last_bar['datetime'])
            else:
                last_dt = pd.to_datetime(last_bar.timestamp)
                
            start_date = last_dt.strftime("%Y-%m-%d")
            print(f"📅 [Engine] 偵測到歷史資料，將從 {start_date} 開始回補...")
        else:
            # 如果完全沒資料，預設抓最近 3 天
            print("📅 [Engine] 無歷史資料，預設回補最近 3 天...")
            start_dt = datetime.datetime.now() - datetime.timedelta(days=3)
            start_date = start_dt.strftime("%Y-%m-%d")

        # 3. 執行回補
        print("🚀 [Engine] 啟動雙軌數據對接 (API Backfill)...")
        recent_bars = self.feeder.fetch_kbars(start_date)
        
        if recent_bars:
            # 4. 將資料倒進策略 (策略會自己處理重複資料)
            # 注意: 這裡假設 strategy.load_history_bars 已經支援 append 模式
            # 如果它是覆蓋模式，我們可能需要先合併。
            # 但我們目前的 BaseStrategy.load_history_bars 是 append 嗎？
            # 檢查後發現 BaseStrategy 是 self.raw_bars = bars (覆蓋)
            # 所以我們要先拿出舊的，合併後再塞回去，或者直接呼叫策略的 update
            
            # 這裡我們用比較安全的方式：直接呼叫 load_history_bars，讓策略自己處理
            # 但為了避免 CSV 資料被洗掉，我們應該把新資料 append 進去
            
            # 修正策略：我們直接把新資料 append 到 strategy.raw_bars
            # (因為 BaseStrategy/MAStrategy 的 raw_bars 是 deque 或 list)
            
            count = 0
            # 取得目前策略最後的時間，用來過濾重複
            last_strategy_time = None
            if self.strategy.raw_bars:
                 last_item = self.strategy.raw_bars[-1]
                 # 確保轉成 pandas timestamp 以便比對
                 if isinstance(last_item, dict):
                     last_strategy_time = pd.to_datetime(last_item['datetime'])
                 else:
                     last_strategy_time = pd.to_datetime(last_item.timestamp)

            print(f"🧐 [Debug] CSV 最後時間: {last_strategy_time}")
            if recent_bars:
                first_api_time = pd.to_datetime(recent_bars[0]['datetime'])
                last_api_time = pd.to_datetime(recent_bars[-1]['datetime'])
                print(f"🧐 [Debug] API 資料範圍: {first_api_time} ~ {last_api_time}")

            # --- 開始比對與接合 ---
            for bar in recent_bars:
                bar_time = pd.to_datetime(bar['datetime']) # 確保也是 Timestamp
                
                # 嚴格過濾：必須比 CSV 最後時間「大」才收
                if last_strategy_time and bar_time <= last_strategy_time:
                    continue
                
                # 轉成策略需要的格式 (dict) 並 append
                self.strategy.raw_bars.append({
                    'datetime': bar['datetime'],
                    'close': bar['close'],
                    # 視需要補上 open/high/low/volume
                    'open': bar['open'],
                    'high': bar['high'],
                    'low': bar['low'],
                    'volume': bar['volume']
                })
                count += 1
            
            print(f"🔗 [Engine] 雙軌對接完成！成功接合 {count} 根 K 棒。")
        #     # --- 🛡️ 資料連續性檢查 (Gap Detection) ---
        #     if count > 0 and last_strategy_time:
        #         # 取得剛接上的第一根新資料時間
        #         # 注意：這裡要從 recent_bars 裡找第一根被 accept 的
        #         # 為了簡化，我們直接比較 CSV最後一根 vs API第一根(如果它比CSV新的話)
                
        #         # 比較簡單的做法：檢查 CSV 最後時間 與 當下時間 的差距
        #         # 如果補完資料後，最新的資料時間距離現在超過 X 分鐘，代表有問題
                
        #         new_last_bar = self.strategy.raw_bars[-1]
        #         new_last_time = pd.to_datetime(new_last_bar['datetime'] if isinstance(new_last_bar, dict) else new_last_bar.timestamp)
        #         now = datetime.datetime.now()
                
        #         # 計算落後多久
        #         lag = now - new_last_time
                
        #         # 如果是盤中 (08:45~13:45)，且落後超過 5 分鐘
        #         is_trading_hours = (8 <= now.hour <= 13) 
        #         if is_trading_hours and lag.total_seconds() > 300: # 5分鐘
        #             warning_msg = f"⚠️ [嚴重警告] 資料可能有斷層！\n最新資料時間: {new_last_time}\n目前系統時間: {now}\n落後: {lag}"
        #             print(warning_msg)
        #             self.commander.send_message(warning_msg)
        #         else:
        #             print(f"✅ [Engine] 資料連續性檢查通過 (Lag: {lag})")

        #     self.commander.send_message(f"🔗 **數據對接完成**\n補回 {count} 根 K 棒 (Warm Data)")
        # else:
        #     print("⚠️ [Engine] 無新資料需回補 (可能已是最新)")

            # ==========================================
            # 🛡️ 新增：資料新鮮度防呆檢查 (Data Freshness Check)
            # ==========================================
            if self.strategy.raw_bars:
                # 1. 取得目前策略記憶體中「最新」的那根 K 棒時間
                last_bar = self.strategy.raw_bars[-1]
                
                # 兼容性處理 (dict vs object)
                if isinstance(last_bar, dict):
                    last_bar_time = pd.to_datetime(last_bar['datetime'])
                else:
                    last_bar_time = pd.to_datetime(last_bar.timestamp)
                
                # 2. 計算落後時間 (Lag)
                now = datetime.datetime.now()
                lag = now - last_bar_time
                
                # 3. 判斷嚴重程度
                # 假設: 如果落後超過 24 小時，通常代表是假日，或者資料嚴重脫節
                msg_header = ""
                should_warn = False
                
                # 情況 A: 盤中 (08:45 ~ 13:45) 且落後超過 10 分鐘 -> 紅色警報
                is_day_trading = (8 <= now.hour <= 13)
                if is_day_trading and lag.total_seconds() > 600: # 10分鐘
                    msg_header = "🔴 **[嚴重警報] 資料嚴重滯後！**"
                    should_warn = True
                
                # 情況 B: 非盤中，但落後超過 5 天 (可能忘記跑 Downloader) -> 黃色警報
                elif lag.days > 5:
                    msg_header = "🟡 **[提醒] 歷史資料過舊**"
                    should_warn = True

                # 4. 發送警告
                if should_warn:
                    warning_msg = (
                        f"{msg_header}\n"
                        f"------------------\n"
                        f"最後資料: {last_bar_time.strftime('%Y-%m-%d %H:%M')}\n"
                        f"系統時間: {now.strftime('%Y-%m-%d %H:%M')}\n"
                        f"資料落後: {lag}\n"
                        f"------------------\n"
                        f"💡 建議: 請檢查是否為休市期間，或執行 universal_downloader 更新 CSV。"
                    )
                    print(warning_msg)
                    if self.enable_telegram:
                        self.commander.send_message(warning_msg)
                else:
                    print(f"✅ [Engine] 資料新鮮度檢查通過 (Lag: {lag})")
            
            else:
                 print("⚠️ [Engine] 策略內無任何 K 棒資料！")

    def start(self):
        print(f"🚀 Engine Started: {self.symbol}")
        self.commander.start_listening()
        self.commander.send_startup_report(
            self.symbol, 
            f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) SL:{self.strategy.stop_loss}"
        )
        
        try:
            self.feeder.connect()

            # 👇👇👇 在這裡插入回補邏輯 👇👇👇
            # 先讀 CSV (Cold)，再讀 API (Warm)
            # load_warmup_data 應該在 main_live.py 呼叫過了
            self.sync_warmup_data_from_api() 
            # 👆👆👆 插入結束 👆👆👆

            if hasattr(self.feeder, 'subscribe'):
                self.feeder.subscribe(self.symbol)
            
            self.feeder.start()
            
            while self.system_running:
                time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n🛑 手動中斷")
            self.commander.send_message("🛑 **系統已手動中斷**")
            self.feeder.stop()