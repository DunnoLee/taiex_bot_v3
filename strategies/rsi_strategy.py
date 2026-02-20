import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class RsiStrategy(BaseStrategy):
    """
    RSI 震盪策略 (測試卡帶)
    邏輯：
    1. 計算 N 根 K 棒的 RSI。
    2. RSI < oversold (預設 30) -> 超賣，進場做多 (或平空單)。
    3. RSI > overbought (預設 70) -> 超買，進場做空 (或平多單)。
    """
    def __init__(self, rsi_period=14, overbought=70, oversold=30, resample=5, stop_loss=300.0):
        super().__init__(name=f"RSI({rsi_period})")
        
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.resample_min = resample
        self.stop_loss = stop_loss
        
        self.raw_bars = deque(maxlen=5000)
        self.silent_mode = True  # 關閉盤中 Debug 避免洗版

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # 1. 檢查停損
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 2. 儲存 K 棒
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'close': bar.close
        })

        # 3. 資料量檢查 (RSI 需要多一點前置資料來平滑)
        required_bars = (self.rsi_period * self.resample_min) + 50
        if len(self.raw_bars) < required_bars:
            return None

        # 4. Resample (跟 MA 策略一模一樣的用法，證明架構相容！)
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        resampled = df['close'].resample(f"{self.resample_min}min").last().dropna()

        if len(resampled) < self.rsi_period + 1:
            return None

        # 5. 計算 RSI (純 Pandas 實作，不依賴外部套件)
        delta = resampled.diff()
        # 漲幅與跌幅分開
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        # 簡單移動平均 (SMA) 版本的 RSI (與 TradingView 略有差異但概念相同)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        if np.isnan(current_rsi): return None

        current_price = bar.close
        signal = None

        # 6. 產生訊號 (RSI 核心邏輯)
        if current_rsi < self.oversold and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                reason=f"Oversold (RSI: {current_rsi:.1f} < {self.oversold})"
            )
            self.entry_price = current_price

        elif current_rsi > self.overbought and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.SHORT,
                strength=1.0,
                reason=f"Overbought (RSI: {current_rsi:.1f} > {self.overbought})"
            )
            self.entry_price = current_price

        return signal

    def _check_stop_loss(self, current_price: float, symbol: str) -> SignalEvent:
        if self.position == 0: return None
        pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
        if pnl <= -self.stop_loss:
            return SignalEvent(
                type=EventType.SIGNAL,
                symbol=symbol, 
                signal_type=SignalType.FLATTEN, 
                reason=f"STOP LOSS triggered (-{self.stop_loss:.0f} pts)"
            )
        return None

    def load_history_bars(self, bars_list: list):
        for bar in bars_list:
            if isinstance(bar, dict):
                self.raw_bars.append({'datetime': bar['datetime'], 'close': bar['close']})
            else:
                self.raw_bars.append({'datetime': bar.timestamp, 'close': bar.close})