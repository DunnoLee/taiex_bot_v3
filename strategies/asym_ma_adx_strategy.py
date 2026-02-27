import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType

class AsymMaAdxStrategy(BaseStrategy):
    """
    【終極雙核心機甲】非對稱多空分離策略 (Asymmetric Dual-Core)
    - 左腦 (做多): 遲鈍長均線 (SMA 300) + 要求爆量突破 (防假突破)
    - 右腦 (做空): 敏銳短均線 (SMA 240) + 無視成交量 (抓無量陰跌)
    """
    def __init__(self, 
                 fast_window=15, 
                 resample=60,         
                 filter_point=100.0,  
                 ma_type_fast="EMA",  
                 ma_type_slow="SMA",  
                 
                 # 🛡️ 左腦 (做多專用)
                 slow_window_long=300,
                 enable_vol_long=True, 
                 
                 # 🗡️ 右腦 (做空專用)
                 slow_window_short=240,
                 enable_vol_short=False,
                 
                 # 共用模組
                 adx_period=14, adx_threshold=25,
                 vol_ma_period=20, vol_multiplier=1.5,
                 
                 # 防禦機制
                 stop_loss=800.0,         
                 enable_trailing_stop=True, 
                 trailing_trigger=300.0,  
                 trailing_dist=300.0      
                 ):
        
        super().__init__(name=f"Asym_DualCore|L({slow_window_long})/S({slow_window_short})")
        
        # --- 綁定核心參數 ---
        self.fast_window = fast_window
        self.slow_window_long = slow_window_long
        self.slow_window_short = slow_window_short
        self.ma_type_fast = ma_type_fast.upper()
        self.ma_type_slow = ma_type_slow.upper() 
        self.filter_point = filter_point
        self.resample_min = resample
        self.stop_loss = stop_loss
        
        # --- 綁定模組參數 ---
        self.enable_vol_long = enable_vol_long
        self.enable_vol_short = enable_vol_short
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.vol_ma_period = vol_ma_period
        self.vol_multiplier = vol_multiplier
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_trigger = trailing_trigger
        self.trailing_dist = trailing_dist
        
        # --- 策略狀態與快取 ---
        self.raw_bars = deque(maxlen=5000)
        self.silent_mode = True
        self.current_bucket_time = None 
        
        # 雙腦快取
        self.cached_ma_fast = None
        self.cached_ma_slow_long = None
        self.cached_ma_slow_short = None
        self.cached_adx = None
        self.cached_vol_ma = None
        self.cached_current_vol = None

        self.bars_resampled = deque(maxlen=25000) 
        self.temp_1m_bars = []                  

        # 防守記憶
        self.highest_price = 0.0
        self.lowest_price = float('inf')

        # 波段鎖定記憶體
        self.last_traded_wave = 0

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        self.latest_price = bar.close
        current_price = bar.close
        
        # ==========================================
        # 🛡️ 執行層：硬停損 & 移動停利
        # ==========================================
        if self.position != 0:
            pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
            if pnl <= -self.stop_loss:
                sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"🩸 硬停損觸發 (-{self.stop_loss:.0f} pts)")
                sig.timestamp = bar.timestamp
                return sig

        if self.enable_trailing_stop and self.position != 0:
            if self.position > 0: 
                self.highest_price = max(self.highest_price, bar.high)
                if (self.highest_price - self.entry_price) >= self.trailing_trigger:
                    if current_price <= (self.highest_price - self.trailing_dist):
                        sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"💰 多單移動停利！(獲利鎖定於 {current_price})")
                        sig.timestamp = bar.timestamp
                        return sig
                        
            elif self.position < 0: 
                self.lowest_price = min(self.lowest_price, bar.low)
                if (self.entry_price - self.lowest_price) >= self.trailing_trigger:
                    if current_price >= (self.lowest_price + self.trailing_dist):
                        sig = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, reason=f"💰 空單移動停利！(獲利鎖定於 {current_price})")
                        sig.timestamp = bar.timestamp
                        return sig

        # ==========================================
        # ⚙️ 運算層：雙腦指標計算 (60分K)
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
                
                # 計算快線
                if self.ma_type_fast == "EMA":
                    self.cached_ma_fast = df_resampled['close'].ewm(span=self.fast_window, adjust=False).mean().iloc[-1]
                else:
                    self.cached_ma_fast = df_resampled['close'].rolling(window=self.fast_window).mean().iloc[-1]

                # 計算 雙慢線
                if self.ma_type_slow == "EMA":
                    self.cached_ma_slow_long = df_resampled['close'].ewm(span=self.slow_window_long, adjust=False).mean().iloc[-1]
                    self.cached_ma_slow_short = df_resampled['close'].ewm(span=self.slow_window_short, adjust=False).mean().iloc[-1]
                else:
                    self.cached_ma_slow_long = df_resampled['close'].rolling(window=self.slow_window_long).mean().iloc[-1]
                    self.cached_ma_slow_short = df_resampled['close'].rolling(window=self.slow_window_short).mean().iloc[-1]

                # 計算 ADX
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

                # 計算成交量
                self.cached_vol_ma = df_resampled['volume'].rolling(window=self.vol_ma_period).mean().iloc[-1]
                self.cached_current_vol = df_resampled['volume'].iloc[-1]

        else:
            self.temp_1m_bars.append(bar)

        # ==========================================
        # 🎯 戰術層：左右腦分離判斷
        # ==========================================
        if self.cached_ma_fast is None or self.cached_ma_slow_long is None: 
            return None

        # --- 狀態更新 ---
        ma_diff_long = self.cached_ma_fast - self.cached_ma_slow_long
        ma_diff_short = self.cached_ma_fast - self.cached_ma_slow_short
        
        # 雙腦波段判定
        wave_long = 1 if ma_diff_long > self.filter_point else 0
        wave_short = -1 if ma_diff_short < -self.filter_point else 0

        # 動態解鎖機制
        if self.last_traded_wave == 1:
            if current_price < self.cached_ma_fast or wave_long == 0:
                self.last_traded_wave = 0
        elif self.last_traded_wave == -1:
            if current_price > self.cached_ma_fast or wave_short == 0:
                self.last_traded_wave = 0

        is_bullish = (wave_long == 1) and (self.last_traded_wave != 1)
        is_bearish = (wave_short == -1) and (self.last_traded_wave != -1)
        
        adx_passed = (self.cached_adx is not None) and (self.cached_adx > self.adx_threshold)
        vol_passed_long = True if not self.enable_vol_long else (self.cached_vol_ma is not None and self.cached_current_vol > self.cached_vol_ma * self.vol_multiplier)
        vol_passed_short = True if not self.enable_vol_short else (self.cached_vol_ma is not None and self.cached_current_vol > self.cached_vol_ma * self.vol_multiplier)

        signal = None
        reason_parts = []

        # 🛡️ 左腦做多 (重裝劍士)
        if is_bullish and adx_passed and vol_passed_long and self.position <= 0 and current_price > self.cached_ma_fast:
            self.last_traded_wave = 1
            reason_parts = [f"做多金叉(+{self.filter_point}點)", f"ADX({self.cached_adx:.1f})"]
            if self.enable_vol_long: reason_parts.append(f"爆量({self.vol_multiplier}x)")
            
            signal = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.LONG, strength=1.0, reason=" | ".join(reason_parts))
            self.entry_price = current_price
            self.highest_price = current_price
            self.lowest_price = current_price

        # 🗡️ 右腦做空 (暗影刺客)
        elif is_bearish and adx_passed and vol_passed_short and self.position >= 0 and current_price < self.cached_ma_fast:
            self.last_traded_wave = -1
            reason_parts = [f"做空死叉(-{self.filter_point}點)", f"ADX({self.cached_adx:.1f})"]
            if not self.enable_vol_short: reason_parts.append("無量刺殺")
            
            signal = SignalEvent(type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.SHORT, strength=1.0, reason=" | ".join(reason_parts))
            self.entry_price = current_price
            self.highest_price = current_price
            self.lowest_price = current_price

        # 💾 每次 K 棒更新完畢，自動存檔
        self.save_state()

        if signal: signal.timestamp = bar.timestamp
        return signal

    def load_history_bars(self, bars_list: list):
        print(f"🧠 [Strategy] 準備消化 {len(bars_list)} 根歷史資料以計算雙核心指標...")
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
        
        fast = f"{self.cached_ma_fast:.1f}" if self.cached_ma_fast else "N/A"
        slow_l = f"{self.cached_ma_slow_long:.1f}" if self.cached_ma_slow_long else "N/A"
        slow_s = f"{self.cached_ma_slow_short:.1f}" if self.cached_ma_slow_short else "N/A"
        print(f"✅ [Strategy] 雙腦暖機完成！快線:{fast} | 多頭慢線:{slow_l} | 空頭慢線:{slow_s}")
        self.load_state() # 👈 暖機完，立刻從專屬檔案還原記憶
        
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