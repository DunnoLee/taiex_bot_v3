import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType

class SmartHoldStrategy(BaseStrategy):
    """
    智慧長抱策略 (The "Leveraged ETF Substitute")
    邏輯：
    1. 將 1分K 聚合成 日線 (Daily Bar)。
    2. 計算 N 日均線 (預設 20日/月線)。
    3. 收盤價 > 月線：做多持有 (Long)。
    4. 收盤價 < 月線：平倉空手 (Flatten)，絕不放空。
    """
    def __init__(self, daily_ma_period=20, stop_loss=800.0, threshold=100.0):
        super().__init__(name=f"SmartHold(Daily MA{daily_ma_period}|T:{threshold})")
        self.daily_ma_period = daily_ma_period
        self.stop_loss = stop_loss 
        self.threshold = threshold  # 新增：100點避震器
        self.raw_bars = deque(maxlen=10000)
        self.silent_mode = True

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # 1. 檢查硬停損 (防止單日極端黑天鵝)
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 2. 儲存 K 棒
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'close': bar.close
        })

        # 3. 確保資料量足夠算日線 (1天約 300 根 1分K)
        required_bars = self.daily_ma_period * 300 
        if len(self.raw_bars) < required_bars:
            return None

        # 4. 關鍵：Resample 成「日線 (1D)」
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        # 用 'D' 聚合成日線，並取每日最後一筆收盤價
        daily_close = df['close'].resample('1D').last().dropna()

        if len(daily_close) < self.daily_ma_period:
            return None

        # 5. 計算日均線 (例如 20日 月線)
        daily_ma = daily_close.rolling(window=self.daily_ma_period).mean().iloc[-1]
        current_price = bar.close

        if np.isnan(daily_ma): return None

        signal = None

        # 6. 核心長抱邏輯 (只有 Long 和 Flatten)
        
        # 情況 A：價格站上月線，且目前空手 -> 進場長抱！
        if current_price > (daily_ma + self.threshold) and self.position <= 0:
            reason_str = f"Bull Market Resumed (P>{daily_ma:.0f}+{self.threshold})"
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.LONG, strength=1.0,
                reason=reason_str
            )
            self.entry_price = current_price

        # 情況 B：價格跌破 (月線 - 避震器) -> 確定不是假跌破，平倉逃命！
        elif current_price < (daily_ma - self.threshold) and self.position > 0:
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.FLATTEN, strength=1.0,
                reason=f"Bear Market Alert (P<{daily_ma:.0f}-{self.threshold}), went to Cash"
            )
            self.entry_price = 0.0

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
                self.raw_bars.append({'datetime': bar['datetime'], 'close': bar['close']})
            else:
                self.raw_bars.append({'datetime': bar.timestamp, 'close': bar.close})