import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class MaAdxStrategy(BaseStrategy):
    """
    雙均線 + ADX 趨勢濾網策略 (The Trend Sniper)
    邏輯：
    1. 計算快慢 MA。
    2. 計算 ADX 判斷趨勢強度。
    3. 只有在 ADX > threshold (如 25) 時，才允許 MA 交叉進場。
    """
    def __init__(self, fast_window=15, slow_window=300, adx_period=14, adx_threshold=30, filter_point=5.0, resample=5, stop_loss=250.0):
        super().__init__(name=f"MA-ADX({fast_window}/{slow_window}|ADX>{adx_threshold})")
        
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.filter_point = filter_point
        self.resample_min = resample
        self.stop_loss = stop_loss
        
        self.raw_bars = deque(maxlen=5000)
        self.silent_mode = True

        # 🚀 效能優化：新增快取變數
        self.current_bucket_time = None 
        self.cached_ma_fast = None
        self.cached_ma_slow = None
        self.cached_adx = None

        # 🚀 效能優化：新增快取與 K 棒壓縮陣列
        self.bars_5m = deque(maxlen=400) # 只存壓縮好的 5 分 K (400根絕對夠算 240MA)
        self.temp_1m_bars = []           # 暫存這 5 分鐘內的 1 分 K

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # 1. 檢查硬停損 (保命符優先)
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 🚀 效能核彈 3.0：【手工 K 棒壓縮機】
        bucket_minute = (bar.timestamp.minute // self.resample_min) * self.resample_min
        bucket_time = bar.timestamp.replace(minute=bucket_minute, second=0, microsecond=0)

        # 判斷是否跨入新的 5 分鐘區間
        if self.current_bucket_time != bucket_time:
            
            # 把上一包 1 分 K 結算成「一根」5 分 K，存入正式陣列
            if self.temp_1m_bars:
                self.bars_5m.append({
                    'high': max(b.high for b in self.temp_1m_bars),
                    'low': min(b.low for b in self.temp_1m_bars),
                    'close': self.temp_1m_bars[-1].close # 最後一筆當收盤
                })
            
            # 清空暫存，放入最新這根 1 分 K，並更新時間標籤
            self.temp_1m_bars = [bar]
            self.current_bucket_time = bucket_time

            # ==========================================
            # 只有當 5 分 K 陣列夠長時，才呼叫 Pandas 算指標
            # ==========================================
            if len(self.bars_5m) >= self.slow_window + self.adx_period * 2:
                # 👉 這裡傳入的已經是純 5 分 K 了，只有短短 300 多筆，瞬間轉完！
                df_5m = pd.DataFrame(self.bars_5m)
                
                # 計算 MA (直接算，完全跳過龜速的 resample！)
                self.cached_ma_fast = df_5m['close'].rolling(window=self.fast_window).mean().iloc[-1]
                self.cached_ma_slow = df_5m['close'].rolling(window=self.slow_window).mean().iloc[-1]

                # 計算 ADX (邏輯不變，但資料量極小)
                df_adx = df_5m.copy()
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

        else:
            # 如果還在同一個 5 分鐘內，就把 1 分 K 繼續丟進暫存包
            self.temp_1m_bars.append(bar)


        # ==========================================
        # 7. 核心戰術邏輯 (使用快取的 MA + ADX 進行判斷)
        # ==========================================
        
        # 如果均線或 ADX 還沒算出來(例如剛開機)，就繼續等
        if self.cached_ma_fast is None or np.isnan(self.cached_ma_fast) or np.isnan(self.cached_adx): 
            return None

        current_price = bar.close
        signal = None
        
        # MA 交叉判斷 (使用最新的 1分K 價格去撞 5分K 的均線)
        is_bullish = self.cached_ma_fast > (self.cached_ma_slow + self.filter_point)
        is_bearish = self.cached_ma_fast < (self.cached_ma_slow - self.filter_point)
        
        # ADX 濾網判斷
        is_trending = self.cached_adx > self.adx_threshold

        # === 【進場/反手邏輯】 ===
        if is_bullish and is_trending and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                reason=f"Golden Cross & Trend Strong (ADX:{self.cached_adx:.1f} > {self.adx_threshold})"
            )
            self.entry_price = current_price

        elif is_bearish and is_trending and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL, 
                symbol=bar.symbol,
                signal_type=SignalType.SHORT,
                strength=1.0,
                reason=f"Death Cross & Trend Strong (ADX:{self.cached_adx:.1f} > {self.adx_threshold})"
            )
            self.entry_price = current_price

        return signal

    def _check_stop_loss(self, current_price: float, symbol: str) -> SignalEvent:
        if self.position == 0: return None
        pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
        if pnl <= -self.stop_loss:
            return SignalEvent(
                type=EventType.SIGNAL, symbol=symbol, signal_type=SignalType.FLATTEN, 
                reason=f"STOP LOSS triggered (-{self.stop_loss:.0f} pts)"
            )
        return None

    def load_history_bars(self, bars_list: list):
        for bar in bars_list:
            if isinstance(bar, dict):
                # 確保載入完整的 OHLCV
                self.raw_bars.append({
                    'datetime': bar.get('datetime'),
                    'open': bar.get('open', bar.get('close')),
                    'high': bar.get('high', bar.get('close')),
                    'low': bar.get('low', bar.get('close')),
                    'close': bar.get('close'),
                    'volume': bar.get('volume', 0)
                })
            else:
                self.raw_bars.append({
                    'datetime': bar.timestamp, 'open': bar.open, 'high': bar.high, 
                    'low': bar.low, 'close': bar.close, 'volume': bar.volume
                })