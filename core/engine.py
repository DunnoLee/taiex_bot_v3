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

            strategy_info = getattr(self.strategy, 'name', 'Unknown Strategy')
            # 如果你想順便印停損，可以用 getattr 安全地拿 (沒有就回傳 N/A)
            sl_info = getattr(self.strategy, 'stop_loss', 'N/A')
            msg = f"🚀 \n策略: {strategy_info} | SL:{sl_info}"
            
            report += msg #f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) | SL:{self.strategy.stop_loss}"
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
            """處理 /buy, /sell 指令 (無限制市價盲狙 + 完整記帳版)"""
            print(f"👋 [Manual] 收到手動交易指令: {action} {qty} 口")
            
            try:
                # 1. 取得價格與時間 (安全模式)
                current_price = getattr(self.strategy, 'latest_price', 0.0)
                current_time = datetime.datetime.now()
                
                if self.strategy.raw_bars:
                    last_bar = self.strategy.raw_bars[-1]
                    current_time = last_bar['datetime'] if isinstance(last_bar, dict) else getattr(last_bar, 'timestamp', current_time)
                
                if current_price == 0.0:
                    warning_msg = "⚠️ 警告：目前無報價，系統將直接以【市價單】盲出！"
                    print(f"🚫 [Manual] {warning_msg}")
                    self.commander.send_message(warning_msg)
                
                # 2. 智慧判斷：如果你持有空單卻按 /buy，自動轉成平倉！
                current_pos = self.strategy.position
                target_signal = None
                
                if action == "BUY":
                    if current_pos < 0: target_signal = SignalType.FLATTEN
                    else: target_signal = SignalType.LONG
                elif action == "SELL":
                    if current_pos > 0: target_signal = SignalType.FLATTEN
                    else: target_signal = SignalType.SHORT

                # 3. 製作軍令狀
                signal = SignalEvent(
                    type=EventType.SIGNAL, 
                    symbol=self.symbol, 
                    signal_type=target_signal, 
                    strength=1.0, 
                    reason=f"Telegram 手動干預 ({action})"
                )

                # 4. 強制執行官下單 & 記錄損益
                pnl_before = self.executor.total_pnl
                msg = ""
                for _ in range(qty):
                    res = self.executor.execute_signal(signal, current_price)
                    if res: msg = res

                pnl_after = self.executor.total_pnl
                realized_pnl = pnl_after - pnl_before
                
                # 5. 🚀 恢復你的完美記帳邏輯：更新策略倉位與停損基準價
                self.strategy.set_position(self.executor.current_position)
                
                if self.strategy.position != 0:
                    self.strategy.entry_price = current_price 
                else:
                    self.strategy.entry_price = 0.0

                # 6. 🚀 恢復你的 CSV 歷史交易紀錄寫入
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

                print(f"✅ [Manual] 執行官處理完畢！")
                self.commander.send_message(f"✅ **手動成交**\n{msg}\n修正後倉位: {self.strategy.position}")

            except Exception as e:
                import traceback
                print(f"❌ [Manual] 發生嚴重錯誤: {e}")
                traceback.print_exc()
                self.commander.send_message(f"❌ 手動下單崩潰: {e}")

        def flatten_position():
            """處理 /flat 指令 (無限制逃命 + 完整記帳版)"""
            current_pos = self.strategy.position
            if current_pos == 0:
                self.commander.send_message("⚪️ **目前已是空手 (Flat)，無需動作**")
                return

            print(f"👋 [Manual] 執行一鍵平倉，目前倉位: {current_pos}")
            
            try:
                # 1. 安全取得價格與時間
                current_price = getattr(self.strategy, 'latest_price', 0.0)
                current_time = datetime.datetime.now()
                
                if self.strategy.raw_bars:
                    last_bar = self.strategy.raw_bars[-1]
                    current_time = last_bar['datetime'] if isinstance(last_bar, dict) else getattr(last_bar, 'timestamp', current_time)

                if current_price == 0.0:
                    self.commander.send_message("⚠️ 警告：目前無報價，將以【市價單】強行平倉逃命！")

                # 2. 製作平倉訊號
                sig_type = SignalType.FLATTEN 
                # 🚀 替換後 (加上明確的變數名稱標籤)：
                signal = SignalEvent(
                    type=EventType.SIGNAL, 
                    symbol=self.symbol, 
                    signal_type=sig_type, 
                    strength=1.0, 
                    reason="Telegram 手動干預 (/flat)"
                )

                # 3. 執行並結算損益
                pnl_before = self.executor.total_pnl
                msg = ""
                res = self.executor.execute_signal(signal, current_price)
                if res: msg = res
                
                pnl_after = self.executor.total_pnl
                realized_pnl = pnl_after - pnl_before

                # 4. 🚀 恢復策略清空與停損重置
                self.strategy.set_position(self.executor.current_position)
                self.strategy.entry_price = 0.0

                # 5. 🚀 恢復 CSV 紀錄
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

                print(f"✅ [Manual] 平倉訊號已送出！")
                self.commander.send_message(f"✅ **已全數平倉**\n{msg}\n實現損益: ${realized_pnl:,.0f}\n目前倉位: {self.strategy.position}")

            except Exception as e:
                import traceback
                print(f"❌ [Manual] 平倉發生嚴重錯誤: {e}")
                traceback.print_exc()
                self.commander.send_message(f"❌ 平倉指令崩潰: {e}")

        def sync_position():
            """處理 /sync 指令 (強制同步真實倉位 + 修復成本價失憶症)"""
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
            
            # 🚀 致命重點防護：修復「失憶症」，如果發現有單但沒成本價，用現在市價當成本！
            if real_pos != 0 and getattr(self.strategy, 'entry_price', 0.0) == 0.0:
                
                # 1. 優先向 Executor 討要真實成本
                real_cost = getattr(self.executor, 'get_real_cost', lambda: 0.0)()
                
                if real_cost > 0:
                    current_price = real_cost
                    cost_source_msg = "API 真實成本"
                else:
                    # 2. 備案：如果 Executor 拿不到，才用當下市價盲猜
                    current_price = getattr(self.strategy, 'latest_price', 0.0)
                    cost_source_msg = "當前市價 (備案)"
                    
                if current_price > 0:
                    self.strategy.entry_price = current_price

                    # 🚀 新增這行：把新成本價也同步給會計師，避免損益計算錯誤！
                    self.executor.avg_price = current_price

                    # 移動停利的基準點也要一起重置 (如果該策略有這些屬性的話)
                    if hasattr(self.strategy, 'highest_price'): self.strategy.highest_price = current_price
                    if hasattr(self.strategy, 'lowest_price'): self.strategy.lowest_price = current_price
                    
                    msg = f"⚠️ [Sync] 已接管未結算部位！成本基準價重新錨定為當前市價: {current_price}"
                    print(msg)
                    self.commander.send_message(msg)
            else:
                # 歸零均價
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
        
        # 🚀 裝甲升級：替 Tick 接收器穿上防彈衣，並加上「第一滴血」偵測
        self._first_tick_received = False
        
        def safe_on_tick(tick):
            try:
                # 偵測第一筆報價，證明 API 真的有送資料過來！
                if not self._first_tick_received:
                    print(f"💧 [診斷] 成功接收到第一筆即時報價！")
                    self._first_tick_received = True
                
                # ==========================================
                # 🔌 萬用轉接頭：把 Dict 偽裝成 Object，並補上 Symbol
                # ==========================================
                if isinstance(tick, dict):
                    class DummyTick: pass
                    t_obj = DummyTick()
                    
                    # 1. 補齊標的名稱 (如果 API 沒傳，就用我們訂閱的 symbol)
                    t_obj.symbol = tick.get('symbol', self.symbol) 
                    
                    # 2. 抄寫價格與時間
                    t_obj.price = tick.get('price', tick.get('close', 0.0))
                    t_obj.volume = tick.get('volume', 1)
                    t_obj.datetime = tick.get('datetime')
                    
                    # 🚀 關鍵修正：Aggregator 認得的名字是 timestamp，不是 datetime！
                    t_obj.timestamp = tick.get('datetime') 
                    
                    # 為了防呆，順便把 datetime 也綁上去，以防其他地方用到
                    t_obj.datetime = t_obj.timestamp 
                    
                    # 將轉接好的物件交給合成器
                    self.aggregator.on_tick(t_obj)
                else:
                    # 如果本來就是物件 (例如回測時)，就直接放行
                    # 但為了安全，如果沒有 symbol 也強制幫它貼上
                    if not hasattr(tick, 'symbol'):
                        tick.symbol = self.symbol
                    self.aggregator.on_tick(tick)
                
            except Exception as e:
                import traceback
                print(f"❌ [Aggregator] 處理 Tick 時發生致命崩潰: {e}")
                traceback.print_exc()

        # 情境 A: Feeder 是餵 Tick 的 (如 ShioajiFeeder)
        if hasattr(self.feeder, 'set_on_tick'):
            self.feeder.set_on_tick(safe_on_tick) # 👈 改綁定我們的防彈版
            print("🔗 [Engine] 已綁定安全版 Tick 接收器！")
        
        # 情境 B: Feeder 是餵 Bar 的 (如 MockFeeder)
        # 我們直接把 Engine 的 on_bar_generated 綁給它
        if hasattr(self.feeder, 'set_on_bar'):
            self.feeder.set_on_bar(self.on_bar_generated)
            
        # Aggregator 產生的 Bar 也要綁定
        self.aggregator.set_on_bar(self.on_bar_generated)

    def load_warmup_data(self, csv_path="data/history/TMF_History.csv"):
        history_bars = load_history_data(csv_path, tail_count=6000)
        if history_bars:
            self.strategy.load_history_bars(history_bars)
            self.commander.send_message(f"✅ **暖機完成**\n已載入 {len(history_bars)} 根歷史 K 棒")
        else:
            print("⚠️ 無歷史資料，策略將從 0 開始累積")

    def on_bar_generated(self, bar: BarEvent):
        if self.enable_telegram:
            icon = "▶️" if self.auto_trading_active else "⏸"
            
            # 🚀 移除 end='\r'，強制換行，確保每一根 K 棒都能穩穩寫入 Log 攔截器！
            print(f"📊 {bar.timestamp.strftime('%H:%M')} C:{int(bar.close)} {icon}")
            
        signal = self.strategy.on_bar(bar)
        
        if signal:
            # ==========================================
            # 🛡️ 觀望模式 (半自動駕駛)：只廣播，不下單
            # ==========================================
            if not self.auto_trading_active:
                print(f"\n🔔 [觀望模式] 偵測到訊號，但不執行下單: {signal.signal_type.name} | {signal.reason}")
                
                if self.enable_telegram and hasattr(self, 'commander') and self.commander:
                    # 判斷一下建議的手動指令
                    suggest_cmd = "/buy" if signal.signal_type == SignalType.LONG else ("/sell" if signal.signal_type == SignalType.SHORT else "/flat")
                    
                    self.commander.send_message(
                        f"🔔 **[觀望模式] 訊號觸發 (未下單)**\n"
                        f"🎯 動作: {signal.signal_type.name}\n"
                        f"📊 標的: {self.symbol} @ {bar.close}\n"
                        f"📝 原因: {signal.reason}\n"
                        f"------------------\n"
                        f"💡 若要手動跟單，請輸入 `{suggest_cmd}`\n"
                        f"▶️ 若要交還兵權恢復自動，請輸入 `/start`"
                    )
                return # 🚀 結束函數，絕對不會呼叫 Executor 下單！

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
            new_warmup_bars = [] # 🚀 準備一個盤子裝新資料

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
            
            # 🚀 關鍵修復：把這盤 API 溫數據，正式交給大腦的消化系統！
            if new_warmup_bars:
                print(f"🧠 [Engine] 準備將 {count} 根 API 溫數據餵給大腦消化...")
                self.strategy.load_history_bars(new_warmup_bars)

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

    def start(self,block=True):
        print(f"🚀 Engine Started: {self.symbol}")
        self.commander.start_listening()
        strategy_info = getattr(self.strategy, 'name', 'Unknown Strategy')
    
        # 如果你想順便印停損，可以用 getattr 安全地拿 (沒有就回傳 N/A)
        sl_info = getattr(self.strategy, 'stop_loss', 'N/A')
        
        msg = f"🚀 引擎啟動\n策略: {strategy_info} | SL:{sl_info}"

        self.commander.send_startup_report(
            self.symbol,msg
            #f"MA({self.strategy.fast_window}/{self.strategy.slow_window}) SL:{self.strategy.stop_loss}"
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
            
            # ==========================================
            # 🚀 終極防護：開機自動對帳 (Auto-Sync)
            # ==========================================
            if hasattr(self.commander, 'sync_position_cb') and self.commander.sync_position_cb:
                # 🛡️ 加上這行判斷：只有實戰模式 (有連接 API) 才需要開機對帳
                if hasattr(self.executor, 'api'):
                    print("\n🔄 [Engine] 系統初始化完成，啟動自動對帳程序...")
                    self.commander.sync_position_cb()
                else:
                    print("\n🎮 [Engine] 模擬模式啟動，初始部位設定為 0。")
            # ==========================================

            # 🚀 把迴圈包進 block 條件裡
            if block:

                while self.system_running:
                    time.sleep(1)
                    # 👈 新增這段檢查邏輯
                    # 檢查 feeder 是否有 running 屬性，如果有且變成 False，代表回放結束了
                    if hasattr(self.feeder, 'running') and not self.feeder.running:
                        print("\n🏁 [Engine] 偵測到歷史資料回放完畢，自動退出主迴圈！")
                        break
                    
        except KeyboardInterrupt:
            print("\n🛑 手動中斷")
            self.commander.send_message("🛑 **系統已手動中斷**")
            self.feeder.stop()

    def inject_flatten_signal(self, reason: str = "強制平倉"):
        """
        [外部按鈕] 允許外部腳本手動注入一個平倉訊號，並走正規管線處理。
        專門用於回測期末結算，或 Telegram 的緊急平倉按鈕。
        """
        if self.strategy.position == 0:
            return # 沒部位就不動作

        # 1. 取得最後一筆價格與時間 (從大腦拿)
        if not self.strategy.raw_bars:
            return
            
        last_bar = self.strategy.raw_bars[-1]
        last_price = float(last_bar['close'] if isinstance(last_bar, dict) else last_bar.close)
        last_time = last_bar['datetime'] if isinstance(last_bar, dict) else getattr(last_bar, 'timestamp', None)
        
        # 紀錄平倉前的狀態 (算損益與寫 Log 用)
        qty_to_close = abs(self.strategy.position)
        pnl_before = self.executor.total_pnl

        # 2. 建立正規的 SignalEvent
        from core.event import SignalEvent, SignalType, EventType
        signal = SignalEvent(
            type=EventType.SIGNAL,
            symbol=self.symbol,
            signal_type=SignalType.FLATTEN,
            reason=reason,
            timestamp=last_time
        )

        # 3. 走正規管線：叫會計師 (Executor) 算錢
        print(f"⚙️ [Engine] 收到外部強制平倉指令: {reason}")
        if self.executor:
            try:
                self.executor.process_signal(signal, last_price)
            except AttributeError:
                self.executor.execute_signal(signal, last_price)
                
        # 計算這筆結算產生的實現損益
        pnl_after = getattr(self.executor, 'total_pnl', pnl_before)
        realized_pnl = pnl_after - pnl_before

        # 4. 走正規管線：叫書記官 (Recorder) 寫 CSV
        if self.recorder:
            self.recorder.write_trade(
                timestamp=last_time,
                symbol=self.symbol,
                action="FLATTEN",
                price=last_price,
                qty=qty_to_close,
                strategy_name=getattr(self.strategy, 'name', 'Engine-Inject'),
                pnl=realized_pnl,
                msg=reason
            )
            
        # 同步策略的部位狀態歸零
        self.strategy.set_position(0)