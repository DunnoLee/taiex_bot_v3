import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType

class UniversalMaStrategy(BaseStrategy):
    """
    【大一統機甲】全功能通用均線策略 (Universal MA)
    包含：大崩跌斷路器、移動停利、對稱/非對稱多空分離、ADX、爆量濾網
    """
    def __init__(self, 
                 # 1. 基礎引擎
                 fast_window=15, resample=60, filter_point=100.0,  
                 ma_type_fast="EMA", ma_type_slow="SMA",  
                 
                 # 2. 多空方向鎖
                 enable_long=True, enable_short=True,
                 
                 # 3. 左腦 (做多專用)
                 slow_window_long=300, enable_vol_long=True, 
                 
                 # 4. 右腦 (做空專用)
                 slow_window_short=240, enable_vol_short=False,
                 
                 # 5. 共用濾網模組 (針對 Resample 大 K 棒)
                 enable_adx=True, adx_period=14, adx_threshold=25,
                 vol_ma_period=20, vol_multiplier=1.5,
                 
                 # 🛡️ 6. 微觀防禦機制 (針對 1 分鐘 K 棒)
                 enable_hard_stop=True,         # 👈 [開關] 硬停損
                 stop_loss=800.0,               # 硬停損點數
                 
                 enable_trailing_stop=True,     # 👈 [開關] 移動停利
                 trailing_trigger=300.0,        # 啟動門檻
                 trailing_dist=300.0,           # 回檔出場距離
                 
                 enable_flash_crash_breaker=True, # 👈 [開關] 暴跌斷路器 (逃命用)
                 flash_crash_threshold=50.0,      # 1分鐘內狂跌超過幾點觸發
                 flash_crash_vol_multiplier=3.0   # 1分鐘成交量超過均量幾倍觸發
                 ):
        
        super().__init__(name=f"Uni_MA|L({slow_window_long})/S({slow_window_short})")
        
        # --- 參數綁定 ---
        self.fast_window, self.resample_min, self.filter_point = fast_window, resample, filter_point
        self.ma_type_fast, self.ma_type_slow = ma_type_fast.upper(), ma_type_slow.upper()
        self.enable_long, self.enable_short = enable_long, enable_short
        self.slow_window_long, self.enable_vol_long = slow_window_long, enable_vol_long
        self.slow_window_short, self.enable_vol_short = slow_window_short, enable_vol_short
        self.enable_adx, self.adx_period, self.adx_threshold = enable_adx, adx_period, adx_threshold
        self.vol_ma_period, self.vol_multiplier = vol_ma_period, vol_multiplier
        
        self.enable_hard_stop, self.stop_loss = enable_hard_stop, stop_loss
        self.enable_trailing_stop, self.trailing_trigger, self.trailing_dist = enable_trailing_stop, trailing_trigger, trailing_dist
        
        # 斷路器參數
        self.enable_flash_crash_breaker = enable_flash_crash_breaker
        self.flash_crash_threshold = flash_crash_threshold
        self.flash_crash_vol_multiplier = flash_crash_vol_multiplier
        
        # --- 快取與記憶體 ---
        self.bars_resampled = deque(maxlen=1000) 
        self.temp_1m_bars = []                  
        self.current_bucket_time = None 
        
        # 專門給斷路器用的「1分鐘微觀均量」記憶體
        self.min_vol_history = deque(maxlen=20) 

        self.cached_ma_fast = self.cached_ma_slow_long = self.cached_ma_slow_short = None
        self.cached_adx = self.cached_vol_ma = self.cached_current_vol = None

        self.highest_price = 0.0
        self.lowest_price = float('inf')
        self.last_traded_wave = 0

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        self.latest_price = bar.close
        current_price = bar.close
        
        # 記錄 1 分鐘的微觀成交量，供斷路器使用
        self.min_vol_history.append(bar.volume)
        avg_1m_vol = sum(self.min_vol_history) / len(self.min_vol_history) if len(self.min_vol_history) > 0 else 1

        # ==========================================
        # 🛡️ 1. 執行層：微觀防禦機制 (1分K 即時掃描)
        # ==========================================
        if self.position != 0:
            
            # [防禦 A] 🚨 大崩跌斷路器 (極速逃生)
            if self.enable_flash_crash_breaker and len(self.min_vol_history) >= 10:
                if self.position > 0:
                    # 多單遇到暴跌砸盤
                    bar_drop = bar.open - bar.close
                    if bar_drop >= self.flash_crash_threshold and bar.volume > (avg_1m_vol * self.flash_crash_vol_multiplier):
                        sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"🌋 斷路器觸發！(1分K暴跌 {bar_drop:.0f}點, 爆量 {bar.volume})")
                        sig.timestamp = bar.timestamp
                        self.save_state()
                        return sig
                elif self.position < 0:
                    # 空單遇到暴力軋空
                    bar_surge = bar.close - bar.open
                    if bar_surge >= self.flash_crash_threshold and bar.volume > (avg_1m_vol * self.flash_crash_vol_multiplier):
                        sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"🌋 斷路器觸發！(1分K暴拉 {bar_surge:.0f}點, 爆量 {bar.volume})")
                        sig.timestamp = bar.timestamp
                        self.save_state()
                        return sig

            # [防禦 B] 🧱 硬停損
            if self.enable_hard_stop:
                pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
                if pnl <= -self.stop_loss:
                    sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"🩸 硬停損觸發 (-{self.stop_loss:.0f} pts)")
                    sig.timestamp = bar.timestamp
                    self.save_state()
                    return sig

            # [防禦 C] 🛡️ 移動停利
            if self.enable_trailing_stop:
                if self.position > 0: 
                    self.highest_price = max(self.highest_price, bar.high)
                    if (self.highest_price - self.entry_price) >= self.trailing_trigger:
                        if current_price <= (self.highest_price - self.trailing_dist):
                            sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"💰 多單移動停利！(鎖定於 {current_price})")
                            sig.timestamp = bar.timestamp
                            self.save_state()
                            return sig
                            
                elif self.position < 0: 
                    self.lowest_price = min(self.lowest_price, bar.low)
                    if (self.entry_price - self.lowest_price) >= self.trailing_trigger:
                        if current_price >= (self.lowest_price + self.trailing_dist):
                            sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"💰 空單移動停利！(鎖定於 {current_price})")
                            sig.timestamp = bar.timestamp
                            self.save_state()
                            return sig

        # ==========================================
        # ⚙️ 2. 運算層：指標計算 (60分K壓縮)
        # ==========================================
        bucket_minute = (bar.timestamp.minute // self.resample_min) * self.resample_min
        bucket_time = bar.timestamp.replace(minute=bucket_minute, second=0, microsecond=0)

        if self.current_bucket_time != bucket_time:
            if self.temp_1m_bars:
                self.bars_resampled.append({
                    'high': max(b.high for b in self.temp_1m_bars),
                    'low': min(b.low for b in self.temp_1m_bars),
                    'close': self.temp_1m_bars[-1].close,
                    'volume': sum(b.volume for b in self.temp_1m_bars)
                })
            self.temp_1m_bars = [bar]
            self.current_bucket_time = bucket_time

            max_window = max(self.slow_window_long, self.slow_window_short) + max(self.adx_period, self.vol_ma_period) * 2
            if len(self.bars_resampled) >= max_window:
                df_resampled = pd.DataFrame(self.bars_resampled)
                
                # 計算 MA
                if self.ma_type_fast == "EMA":
                    self.cached_ma_fast = df_resampled['close'].ewm(span=self.fast_window, adjust=False).mean().iloc[-1]
                else:
                    self.cached_ma_fast = df_resampled['close'].rolling(window=self.fast_window).mean().iloc[-1]

                if self.ma_type_slow == "EMA":
                    self.cached_ma_slow_long = df_resampled['close'].ewm(span=self.slow_window_long, adjust=False).mean().iloc[-1]
                    self.cached_ma_slow_short = df_resampled['close'].ewm(span=self.slow_window_short, adjust=False).mean().iloc[-1]
                else:
                    self.cached_ma_slow_long = df_resampled['close'].rolling(window=self.slow_window_long).mean().iloc[-1]
                    self.cached_ma_slow_short = df_resampled['close'].rolling(window=self.slow_window_short).mean().iloc[-1]

                # 計算 ADX
                if self.enable_adx:
                    df_adx = df_resampled.copy()
                    df_adx['prev_close'] = df_adx['close'].shift(1)
                    df_adx['tr1'] = df_adx['high'] - df_adx['low']
                    df_adx['tr2'] = (df_adx['high'] - df_adx['prev_close']).abs()
                    df_adx['tr3'] = (df_adx['low'] - df_adx['prev_close']).abs()
                    df_adx['tr'] = df_adx[['tr1', 'tr2', 'tr3']].max(axis=1)
                    df_adx['up_move'] = df_adx['high'] - df_adx['high'].shift(1)
                    df_adx['down_move'] = df_adx['low'].shift(1) - df_adx['low']
                    df_adx['+dm'] = np.where((df_adx['up_move'] > df_adx['down_move']) & (df_adx['up_move'] > 0), df_adx['up_move'], 0)
                    df_adx['-dm'] = np.where((df_adx['down_move'] > df_adx['up_move']) & (df_adx['down_move'] > 0), df_adx['down_move'], 0)
                    atr = df_adx['tr'].ewm(span=self.adx_period, adjust=False).mean()
                    plus_di = 100 * (df_adx['+dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
                    minus_di = 100 * (df_adx['-dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
                    di_sum = plus_di + minus_di
                    di_sum = di_sum.replace(0, np.nan) 
                    dx = 100 * (abs(plus_di - minus_di) / di_sum)
                    self.cached_adx = dx.ewm(span=self.adx_period, adjust=False).mean().iloc[-1]

                # 計算 60分K 大顆粒成交量
                self.cached_vol_ma = df_resampled['volume'].rolling(window=self.vol_ma_period).mean().iloc[-1]
                self.cached_current_vol = df_resampled['volume'].iloc[-1]
        else:
            self.temp_1m_bars.append(bar)

        # ==========================================
        # 🎯 3. 戰術層：雙向進場邏輯判定
        # ==========================================
        if self.cached_ma_fast is None or self.cached_ma_slow_long is None: 
            return None

        ma_diff_long = self.cached_ma_fast - self.cached_ma_slow_long
        ma_diff_short = self.cached_ma_fast - self.cached_ma_slow_short
        
        wave_long = 1 if ma_diff_long > self.filter_point else 0
        wave_short = -1 if ma_diff_short < -self.filter_point else 0

        if self.last_traded_wave == 1:
            if current_price < self.cached_ma_fast or wave_long == 0: self.last_traded_wave = 0
        elif self.last_traded_wave == -1:
            if current_price > self.cached_ma_fast or wave_short == 0: self.last_traded_wave = 0

        is_bullish = (wave_long == 1) and (self.last_traded_wave != 1)
        is_bearish = (wave_short == -1) and (self.last_traded_wave != -1)
        
        adx_passed = True if not self.enable_adx else (self.cached_adx is not None and self.cached_adx > self.adx_threshold)
        vol_passed_long = True if not self.enable_vol_long else (self.cached_vol_ma is not None and self.cached_current_vol > self.cached_vol_ma * self.vol_multiplier)
        vol_passed_short = True if not self.enable_vol_short else (self.cached_vol_ma is not None and self.cached_current_vol > self.cached_vol_ma * self.vol_multiplier)

        signal = None
        reason_parts = []

        if self.enable_long and is_bullish and adx_passed and vol_passed_long and self.position <= 0 and current_price > self.cached_ma_fast:
            self.last_traded_wave = 1
            reason_parts = [f"做多金叉(+{self.filter_point})"]
            if self.enable_adx: reason_parts.append(f"ADX({self.cached_adx:.1f})")
            if self.enable_vol_long: reason_parts.append(f"爆量({self.vol_multiplier}x)")
            
            signal = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.LONG, strength=1.0, reason=" | ".join(reason_parts))
            self.entry_price = self.highest_price = self.lowest_price = current_price

        elif self.enable_short and is_bearish and adx_passed and vol_passed_short and self.position >= 0 and current_price < self.cached_ma_fast:
            self.last_traded_wave = -1
            reason_parts = [f"做空死叉(-{self.filter_point})"]
            if self.enable_adx: reason_parts.append(f"ADX({self.cached_adx:.1f})")
            if self.enable_vol_short: reason_parts.append(f"爆量({self.vol_multiplier}x)")
            
            signal = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.SHORT, strength=1.0, reason=" | ".join(reason_parts))
            self.entry_price = self.highest_price = self.lowest_price = current_price

        if signal: signal.timestamp = bar.timestamp
        self.save_state() 
        return signal

    def load_history_bars(self, bars_list: list):
        print(f"🧠 [Strategy] 消化 {len(bars_list)} 根歷史資料暖機中...")
        orig_pos, orig_entry = getattr(self, 'position', 0), getattr(self, 'entry_price', 0.0)
        orig_high, orig_low = getattr(self, 'highest_price', 0.0), getattr(self, 'lowest_price', float('inf'))
        orig_wave = getattr(self, 'last_traded_wave', 0)
        self.position = 0 
        
        for bar in bars_list:
            if isinstance(bar, dict):
                from core.event import BarEvent
                bar = BarEvent(symbol='TMF', timestamp=bar.get('datetime'), open=bar.get('open'), high=bar.get('high'), low=bar.get('low'), close=bar.get('close'), volume=bar.get('volume', 0))
            self.on_bar(bar)
            
        self.position, self.entry_price = orig_pos, orig_entry
        self.highest_price, self.lowest_price, self.last_traded_wave = orig_high, orig_low, orig_wave
        print(f"✅ [Strategy] 暖機完成！")
        
        # ⚠️ 防呆載入記憶
        if hasattr(self, 'load_state'):
            self.load_state()

    def get_ui_dict(self):
        price = getattr(self, 'latest_price', 0.0)
        fast = getattr(self, 'cached_ma_fast', None)
        slow_l = getattr(self, 'cached_ma_slow_long', None)
        slow_s = getattr(self, 'cached_ma_slow_short', None)
        adx = getattr(self, 'cached_adx', None)
        vol = getattr(self, 'cached_current_vol', None)
        
        if fast is None or slow_l is None or np.isnan(fast):
            return {"💰 目前報價": f"{price}", "⏳ 系統狀態": "雙腦歷史資料暖機中..."}
            
        diff_l = fast - slow_l
        diff_s = fast - slow_s
        
        # 動態顯示優勢方
        if diff_l > self.filter_point: ma_status = f"[green]多頭掌權 (+{diff_l:.1f})[/green]"
        elif diff_s < -self.filter_point: ma_status = f"[red]空頭掌權 ({diff_s:.1f})[/red]"
        else: ma_status = f"[yellow]多空交戰區 (多{diff_l:.0f} / 空{diff_s:.0f})[/yellow]"

        adx_str = f"[bold red]🔥 {adx:.1f} (爆發)[/bold red]" if adx and adx > self.adx_threshold else f"🧊 {adx:.1f} (盤整)" if adx else "N/A"
        lock_str = "🔒 已鎖定波段" if getattr(self, 'last_traded_wave', 0) != 0 else "🔓 尋找獵物中"

        defense_str, pnl_str = "⚪️ 無部位", "0 pts"
        if self.position != 0 and hasattr(self, 'entry_price') and self.entry_price > 0:
            pnl = (price - self.entry_price) if self.position > 0 else (self.entry_price - price)
            pnl_color = "green" if pnl > 0 else "red"
            pnl_str = f"[{pnl_color}]{pnl:.0f} pts[/{pnl_color}]"
            
            if self.position > 0:
                high_p = getattr(self, 'highest_price', self.entry_price)
                if self.enable_trailing_stop and (high_p - self.entry_price) >= self.trailing_trigger:
                    defense_str = f"🛡️ 移動停利 (高點 {high_p:.0f} 回檔 {self.trailing_dist})"
                else:
                    defense_str = f"🧱 硬停損 (跌破 {self.entry_price - self.stop_loss:.0f})"
            else:
                low_p = getattr(self, 'lowest_price', self.entry_price)
                if self.enable_trailing_stop and (self.entry_price - low_p) >= self.trailing_trigger:
                    defense_str = f"🛡️ 移動停利 (低點 {low_p:.0f} 反彈 {self.trailing_dist})"
                else:
                    defense_str = f"🧱 硬停損 (突破 {self.entry_price + self.stop_loss:.0f})"

        return {
            "💰 目前報價": f"{price}",
            "🎯 策略狀態": lock_str,
            "⚡️ 雙腦戰局": ma_status,
            "🔥 ADX 強度": adx_str,
            "📊 當前爆量": f"{vol}" if vol else "N/A",
            "📈 帳面損益": pnl_str,
            "🛡️ 防守陣線": defense_str
        }