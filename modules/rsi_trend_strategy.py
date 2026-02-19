import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class RsiTrendStrategy(BaseStrategy):
    """
    RSI 順勢拉回策略 (The Pullback Strategy)
    結合 MA(趨勢濾網) 與 RSI(精準轉折) 的雙劍合璧卡帶。
    """
    def __init__(self, ma_period=240, rsi_period=14, overbought=70, oversold=30, resample=5, stop_loss=300.0):
        # 命名卡帶，方便在 Telegram 和 Log 辨識
        super().__init__(name=f"RsiTrend({ma_period}/{rsi_period})")
        
        self.ma_period = ma_period
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.resample_min = resample
        self.stop_loss = stop_loss
        
        self.raw_bars = deque(maxlen=5000)
        self.silent_mode = True

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # 1. 檢查硬停損 (保命符)
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 2. 儲存 K 棒
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'close': bar.close
        })

        # 3. 資料量檢查 (需要滿足 MA 的長度)
        required_bars = (self.ma_period * self.resample_min) + 50
        if len(self.raw_bars) < required_bars:
            return None

        # 4. Resample (將 1分K 轉為 5分K)
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        resampled = df['close'].resample(f"{self.resample_min}min").last().dropna()

        if len(resampled) < self.ma_period:
            return None

        # 5. 計算指標
        current_price = bar.close
        
        # A. 計算 MA (長線趨勢)
        ma_trend = resampled.rolling(window=self.ma_period).mean().iloc[-1]
        
        # B. 計算 RSI (短線轉折)
        delta = resampled.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        current_rsi = (100 - (100 / (1 + rs))).iloc[-1]

        if np.isnan(ma_trend) or np.isnan(current_rsi): return None

        signal = None

        # 6. 核心戰術邏輯 (The Logic)
        
        # 狀態 A：判斷大趨勢
        is_bull_market = current_price > ma_trend  # 多頭市場
        is_bear_market = current_price < ma_trend  # 空頭市場

        # === 【進場邏輯】 ===
        # 多頭市場中，發生暴跌 (RSI 超賣) -> 勇敢做多！
        if is_bull_market and current_rsi < self.oversold and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.LONG, strength=1.0,
                reason=f"Buy the Dip (P>{ma_trend:.0f} & RSI:{current_rsi:.1f}<{self.oversold})"
            )
            self.entry_price = current_price

        # 空頭市場中，發生暴漲 (RSI 超買) -> 勇敢放空！
        elif is_bear_market and current_rsi > self.overbought and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.SHORT, strength=1.0,
                reason=f"Sell the Rally (P<{ma_trend:.0f} & RSI:{current_rsi:.1f}>{self.overbought})"
            )
            self.entry_price = current_price

        # === 【出場邏輯 (停利)】 ===
        # 如果手上有「多單」，且 RSI 已經反彈到 55 以上 (不貪心，有賺就跑) -> 平倉
        elif self.position > 0 and current_rsi > 55:
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.FLATTEN, strength=1.0,
                reason=f"Take Profit (RSI recovered to {current_rsi:.1f})"
            )
            self.entry_price = 0.0

        # 如果手上有「空單」，且 RSI 已經跌到 45 以下 -> 平倉
        elif self.position < 0 and current_rsi < 45:
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol,
                signal_type=SignalType.FLATTEN, strength=1.0,
                reason=f"Take Profit (RSI dropped to {current_rsi:.1f})"
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