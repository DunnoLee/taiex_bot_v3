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
    def __init__(self, fast_window=30, slow_window=240, adx_period=14, adx_threshold=25, filter_point=5.0, resample=5, stop_loss=300.0):
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

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # 1. 檢查硬停損 (保命符優先)
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 2. 儲存 K 棒 (ADX 需要最高最低價)
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        })

        # 3. 資料量檢查
        required_bars = (self.slow_window * self.resample_min) + 50
        if len(self.raw_bars) < required_bars:
            return None

        # 4. Resample (將 1分K 轉為 5分K)
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        
        # 針對 OHLC 進行正確的 Resample
        resampled = df.resample(f"{self.resample_min}min").agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()

        if len(resampled) < self.slow_window:
            return None

        # 5. 計算 MA
        ma_fast = resampled['close'].rolling(window=self.fast_window).mean().iloc[-1]
        ma_slow = resampled['close'].rolling(window=self.slow_window).mean().iloc[-1]

        # 6. 計算 ADX (免依賴 TA-Lib，純 Pandas 實作)
        df_adx = resampled.copy()
        df_adx['prev_close'] = df_adx['close'].shift(1)
        
        # True Range (TR)
        df_adx['tr1'] = df_adx['high'] - df_adx['low']
        df_adx['tr2'] = (df_adx['high'] - df_adx['prev_close']).abs()
        df_adx['tr3'] = (df_adx['low'] - df_adx['prev_close']).abs()
        df_adx['tr'] = df_adx[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Directional Movement (+DM, -DM)
        df_adx['up_move'] = df_adx['high'] - df_adx['high'].shift(1)
        df_adx['down_move'] = df_adx['low'].shift(1) - df_adx['low']
        
        df_adx['+dm'] = np.where((df_adx['up_move'] > df_adx['down_move']) & (df_adx['up_move'] > 0), df_adx['up_move'], 0)
        df_adx['-dm'] = np.where((df_adx['down_move'] > df_adx['up_move']) & (df_adx['down_move'] > 0), df_adx['down_move'], 0)
        
        # Smoothing (使用 EMA 近似 Wilder's Smoothing 以增進效能)
        atr = df_adx['tr'].ewm(span=self.adx_period, adjust=False).mean()
        plus_di = 100 * (df_adx['+dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
        minus_di = 100 * (df_adx['-dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
        
        # 避免除以零
        di_sum = plus_di + minus_di
        di_sum = di_sum.replace(0, np.nan) 
        dx = 100 * (abs(plus_di - minus_di) / di_sum)
        adx = dx.ewm(span=self.adx_period, adjust=False).mean()
        
        current_adx = adx.iloc[-1]
        current_price = bar.close

        if np.isnan(ma_fast) or np.isnan(current_adx): return None

        # 7. 核心戰術邏輯 (MA + ADX)
        signal = None
        
        # MA 交叉判斷 (跟原本一樣)
        is_bullish = ma_fast > (ma_slow + self.filter_point)
        is_bearish = ma_fast < (ma_slow - self.filter_point)
        
        # ADX 濾網判斷
        is_trending = current_adx > self.adx_threshold

        # === 【進場/反手邏輯】 ===
        # 只有在「有趨勢 (ADX>25)」的時候，我們才相信 MA 的交叉訊號
        if is_bullish and is_trending and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,  # 嚴格遵守 type 命名
                symbol=bar.symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                reason=f"Golden Cross & Trend Strong (ADX:{current_adx:.1f} > {self.adx_threshold})"
            )
            self.entry_price = current_price

        elif is_bearish and is_trending and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL, 
                symbol=bar.symbol,
                signal_type=SignalType.SHORT,
                strength=1.0,
                reason=f"Death Cross & Trend Strong (ADX:{current_adx:.1f} > {self.adx_threshold})"
            )
            self.entry_price = current_price

        # === 【平倉邏輯 (選配)】 ===
        # 當趨勢消失 (ADX < 20)，且目前有部位時，可以選擇提早入袋為安，不等到被 MA 死亡交叉洗出去。
        # 為了比較純粹的 ADX 濾網效果，我們目前先依賴停損和反手，維持跟純 MA 策略最接近的架構。

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