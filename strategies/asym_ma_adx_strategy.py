from core.base_strategy import BaseStrategy
from core.event import SignalEvent, SignalType, EventType
import pandas as pd
import pandas_ta as ta
from collections import deque

class AsymMaAdxStrategy(BaseStrategy):
    def __init__(self, fast_window=10, slow_window=300, regime_window=1200, adx_window=14, adx_threshold=25.0, vol_multiplier=1.5):
        super().__init__()
        self.name = f"Asym_MA({fast_window}/{slow_window})_Regime({regime_window})"
        
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.regime_window = regime_window
        self.adx_window = adx_window
        self.adx_threshold = adx_threshold
        self.vol_multiplier = vol_multiplier
        
        # 🟢 做多專用參數 (緩漲：寬容進場，寬容防守)
        self.long_filter_point = 80.0     
        self.long_stop_loss = -400.0           # 剛進場時，容忍 400 點的洗盤
        self.long_trailing_activate = 200.0    # 🚀 新增：帳面獲利達到 200 點才啟動移動停利！
        self.long_trailing_dist = 150.0        # 🚀 修改：啟動後，只要從最高點回檔 150 點就獲利了結
        
        # 🔴 做空專用參數 (急跌：敏銳進場，神經質防守)
        self.short_filter_point = 40.0    
        self.short_stop_loss = -200.0          # 空單只容忍 200 點的洗盤 (防軋空)
        self.short_trailing_activate = 100.0   # 🚀 新增：空單獲利 100 點就啟動
        self.short_trailing_dist = 80.0        # 🚀 修改：啟動後，只要從最低點反彈 80 點就趕快跑！

        # 🚀 終極優化：只保留 15分K 的陣列，將資料量從 20000 壓縮到 1500！
        self.bars_15m = deque(maxlen=1500) 
        self.current_15m = None # 正在成型中的那根 15 分 K
        
        self.cached_ma_fast = 0.0
        self.cached_ma_slow = 0.0
        self.cached_regime_ma = 0.0
        self.cached_adx = 0.0
        self.wave_locked = False

    def on_bar(self, bar):
        self.latest_price = bar.close

        # ==========================================
        # ⚡️ 1. 極速增量合成 15 分 K (完全避開 Pandas Resample)
        # ==========================================
        bar_time = bar.timestamp
        # 算出這根 1 分 K 屬於哪個 15 分鐘的區段 (例如 10:17 會被歸類到 10:15)
        slot_min = (bar_time.minute // 15) * 15
        slot_time = bar_time.replace(minute=slot_min, second=0, microsecond=0)

        if self.current_15m is None or self.current_15m['datetime'] != slot_time:
            # 時間跨入新的 15 分鐘：把舊的封裝進歷史陣列，建立新的
            if self.current_15m is not None:
                self.bars_15m.append(self.current_15m)
            self.current_15m = {
                'datetime': slot_time,
                'open': bar.open, 'high': bar.high, 'low': bar.low,
                'close': bar.close, 'volume': bar.volume
            }
        else:
            # 同一個 15 分鐘內：只更新高低點與收盤價
            self.current_15m['high'] = max(self.current_15m['high'], bar.high)
            self.current_15m['low'] = min(self.current_15m['low'], bar.low)
            self.current_15m['close'] = bar.close
            self.current_15m['volume'] += bar.volume

        # 把歷史 15分K 和當下這根未完成的 15分K 接起來
        all_15m = list(self.bars_15m) + [self.current_15m]

        if len(all_15m) < self.regime_window:
            return None

        # ==========================================
        # ⚡️ 2. 輕量級指標運算 (只算 1200 行，極度流暢)
        # ==========================================
        df_15m = pd.DataFrame(all_15m)
        df_15m.set_index('datetime', inplace=True)

        df_15m['ma_fast'] = ta.sma(df_15m['close'], length=self.fast_window)
        df_15m['ma_slow'] = ta.sma(df_15m['close'], length=self.slow_window)
        df_15m['regime_ma'] = ta.sma(df_15m['close'], length=self.regime_window)
        
        adx_df = ta.adx(df_15m['high'], df_15m['low'], df_15m['close'], length=self.adx_window)
        df_15m['adx'] = adx_df[f'ADX_{self.adx_window}'] if adx_df is not None else 0.0
        df_15m['vol_ma'] = ta.sma(df_15m['volume'], length=20)

        last_15m = df_15m.iloc[-1]
        self.cached_ma_fast = last_15m['ma_fast']
        self.cached_ma_slow = last_15m['ma_slow']
        self.cached_regime_ma = last_15m['regime_ma']
        self.cached_adx = last_15m['adx']
        
        current_price = bar.close
        ma_diff = self.cached_ma_fast - self.cached_ma_slow
        is_high_vol = last_15m['volume'] > (last_15m['vol_ma'] * self.vol_multiplier)

        # ==========================================
        # 🛡️ 3. 防守與進場邏輯 (動態切換多空防守與啟動點)
        # ==========================================
        if self.position != 0:
            if self.position > 0:
                # 🟢 --- 多單防守 ---
                self.highest_price = max(getattr(self, 'highest_price', current_price), current_price)
                drawdown = current_price - self.highest_price # 從高點回檔的幅度 (負數)
                pnl_points = current_price - self.entry_price # 目前帳面損益點數

                # 1. 檢查硬停損 (隨時生效：容忍 400 點洗盤)
                if pnl_points <= self.long_stop_loss:
                    self.wave_locked = False
                    return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, strength=1.0, reason=f"多單硬停損 ({pnl_points:.0f} pts)")
                
                # 2. 檢查移動停利 (🚀 關鍵：獲利超過 200 點才啟動防護罩)
                if pnl_points >= self.long_trailing_activate:
                    if drawdown <= -self.long_trailing_dist:
                        self.wave_locked = False
                        return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, strength=1.0, reason=f"多單移動停利 (回檔 {abs(drawdown):.0f} pts)")

            else:
                # 🔴 --- 空單防守 ---
                self.lowest_price = min(getattr(self, 'lowest_price', current_price), current_price)
                drawdown = current_price - self.lowest_price # 從低點反彈的幅度 (正數)
                pnl_points = self.entry_price - current_price # 空單帳面損益點數

                # 1. 檢查硬停損 (隨時生效：容忍 200 點洗盤)
                if pnl_points <= self.short_stop_loss:
                    self.wave_locked = False
                    return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, strength=1.0, reason=f"空單硬停損 ({pnl_points:.0f} pts)")
                
                # 2. 檢查移動停利 (🚀 關鍵：獲利超過 100 點才啟動防護罩)
                if pnl_points >= self.short_trailing_activate:
                    if drawdown >= self.short_trailing_dist:  # 空單反彈是正數
                        self.wave_locked = False
                        return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, strength=1.0, reason=f"空單移動停利 (反彈 {drawdown:.0f} pts)")

        # ==========================================
        # 🎯 4. 進場邏輯
        # ==========================================
        # 解鎖邏輯：如果快慢線糾纏在一起，代表趨勢暫歇，解鎖準備下一次進場
        if abs(ma_diff) < self.short_filter_point:
            self.wave_locked = False

        if not self.wave_locked and self.position == 0:
            # 🟢 多頭進場條件
            is_bullish = (ma_diff > self.long_filter_point) and (self.cached_adx > self.adx_threshold)
            is_above_regime = current_price > self.cached_regime_ma
            
            if is_bullish and is_high_vol and is_above_regime:
                self.wave_locked = True
                self.entry_price = current_price
                self.highest_price = current_price
                return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.LONG, strength=1.0, reason="多頭成型 (站上生命線)")

            # 🔴 空頭進場條件
            is_bearish = (ma_diff < -self.short_filter_point) and (self.cached_adx > self.adx_threshold)
            is_below_regime = current_price < self.cached_regime_ma

            if is_bearish and is_high_vol and is_below_regime:
                self.wave_locked = True
                self.entry_price = current_price
                self.lowest_price = current_price
                return SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.SHORT, strength=1.0, reason="空頭成型 (跌破生命線)")

        return None
    
    def get_ui_dict(self):
        """提供給 Rich 儀表板的專屬全息即時數據"""
        price = getattr(self, 'latest_price', 0.0)
        ma_fast = getattr(self, 'cached_ma_fast', 0.0)
        ma_slow = getattr(self, 'cached_ma_slow', 0.0)
        regime = getattr(self, 'cached_regime_ma', 0.0)
        adx = getattr(self, 'cached_adx', 0.0)
        
        # 1. 如果還在暖機，直接回傳等待畫面
        if ma_fast == 0.0:
            return {
                "💰 目前報價": f"{price}",
                "⏳ 系統狀態": "歷史資料暖機計算中..."
            }
            
        # 2. 趨勢與濾網判定
        trend_str = "[red]偏空[/red]" if ma_fast < ma_slow else "[green]偏多[/green]"
        regime_str = "[red]跌破[/red]" if price < regime else "[green]站上[/green]"
        adx_str = f"[bold red]🔥 {adx:.1f} (爆發)[/bold red]" if adx > self.adx_threshold else f"🧊 {adx:.1f} (盤整)"
        lock_str = "🔒 鎖定中" if self.wave_locked else "🔓 尋找獵物"

        # 3. 防守與損益狀態
        defense_str = "⚪️ 無部位"
        pnl_str = "0 pts"
        
        if self.position != 0 and hasattr(self, 'entry_price') and self.entry_price > 0:
            pnl = (price - self.entry_price) if self.position > 0 else (self.entry_price - price)
            pnl_color = "green" if pnl > 0 else "red"
            pnl_str = f"[{pnl_color}]{pnl:.0f} pts[/{pnl_color}]"
            
            if self.position > 0:
                high_p = getattr(self, 'highest_price', self.entry_price)
                if pnl >= getattr(self, 'long_trailing_activate', 0):
                    defense_str = f"🛡️ 移動停利 (高點 {high_p:.0f} 回檔 {self.long_trailing_dist} 出場)"
                else:
                    defense_str = f"🧱 硬停損 (跌破 {self.entry_price + self.long_stop_loss:.0f} 出場)"
            else:
                low_p = getattr(self, 'lowest_price', self.entry_price)
                if pnl >= getattr(self, 'short_trailing_activate', 0):
                    defense_str = f"🛡️ 移動停利 (低點 {low_p:.0f} 反彈 {self.short_trailing_dist} 出場)"
                else:
                    defense_str = f"🧱 硬停損 (突破 {self.entry_price - self.short_stop_loss:.0f} 出場)"

        # 4. 組裝回傳字典 (這裡的 Key 會直接變成儀表板上的標題)
        return {
            "💰 目前報價": f"{price}",
            "🎯 策略狀態": lock_str,
            "⚡️ 快線(15m)": f"{ma_fast:.1f}",
            "🐢 慢線(15m)": f"{ma_slow:.1f} [{trend_str}]",
            "🌍 生命線(60d)": f"{regime:.1f} [{regime_str}]",
            "🔥 ADX 強度": adx_str,
            "📈 帳面損益": pnl_str,
            "🛡️ 防守陣線": defense_str
        }
    