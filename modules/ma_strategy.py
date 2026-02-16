import pandas as pd
import numpy as np
from collections import deque
from core.strategy import BaseStrategy
from core.event import BarEvent, TickEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class MAStrategy(BaseStrategy):
    """
    雙均線策略 V3.4 (Fix Argument Shift)
    
    修正:
    1. SignalEvent 實例化改為「關鍵字參數 (Keyword Arguments)」，防止欄位錯位。
    2. 解決 mock_executor 讀到錯誤 signal_type 的問題。
    """
    def __init__(self, fast_window=None, slow_window=None, threshold=None, resample=None, stop_loss=None):
        name = f"MA({fast_window or 30}/{slow_window or 240})" # 修改顯示名稱
        super().__init__(name)
        
        # 讀取 Settings，如果 Settings 沒定義就用冠軍參數當預設
        self.fast_window = fast_window if fast_window else getattr(Settings, 'STRATEGY_MA_FAST', 30)
        self.slow_window = slow_window if slow_window else getattr(Settings, 'STRATEGY_MA_SLOW', 240)
        self.threshold = threshold if threshold is not None else getattr(Settings, 'STRATEGY_THRESHOLD', 5.0)
        self.resample_min = resample if resample else getattr(Settings, 'STRATEGY_RESAMPLE_MIN', 5)
        
        # 讓 Stop Loss 也能被優化
        self.stop_loss = stop_loss if stop_loss else getattr(Settings, 'STOP_LOSS_POINT', 400.0)

        self.raw_bars = deque(maxlen=2000)
        self.entry_price = 0.0
        
        # 增加一個靜音模式旗標，優化時不要印那些 Debug 訊息
        self.silent_mode = True

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        if not self.active: return None
        
        # 1. 檢查硬止損
        sl_signal = self._check_stop_loss(bar.close)
        if sl_signal: return sl_signal

        # 2. 儲存資料
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'close': bar.close
        })

        # 3. 資料量檢查
        if len(self.raw_bars) < (self.slow_window * self.resample_min):
            return None

        # 4. 執行 Resample
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        resampled = df['close'].resample(f"{self.resample_min}min").last().dropna()

        if len(resampled) < self.slow_window:
            return None

        # 5. 計算 MA
        ma_fast = resampled.rolling(window=self.fast_window).mean().iloc[-1]
        ma_slow = resampled.rolling(window=self.slow_window).mean().iloc[-1]
        
        if np.isnan(ma_fast) or np.isnan(ma_slow): return None

        current_price = resampled.iloc[-1]

        # 6. 產生訊號
        signal = None
        diff = ma_fast - ma_slow
        is_bullish = diff > self.threshold
        is_bearish = diff < -self.threshold

        # Debug 顯示
        if bar.timestamp.minute == 0 and bar.timestamp.second == 0:
            status = "WAIT"
            if is_bullish: status = "BULL ZONE"
            if is_bearish: status = "BEAR ZONE"
            if not self.silent_mode:
                print(f"🕵️ [Debug {bar.timestamp.strftime('%H:%M')}] Price:{current_price:.0f} | Diff:{diff:.1f} ({status})")

        # 進場邏輯 (使用關鍵字參數修復錯位問題)
        if is_bullish and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,          # 明確指定 type
                symbol=bar.symbol,              # 明確指定 symbol
                signal_type=SignalType.LONG,    # 明確指定 signal_type
                strength=1.0,
                reason=f"Bullish: Diff {diff:.1f} > {self.threshold}"
            )
            self.entry_price = current_price

        elif is_bearish and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.SHORT,
                strength=1.0,
                reason=f"Bearish: Diff {diff:.1f} < -{self.threshold}"
            )
            self.entry_price = current_price

        return signal

    def _check_stop_loss(self, current_price: float) -> SignalEvent:
        if self.position == 0: return None
        pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
        
        if pnl <= -self.stop_loss:
            self.entry_price = 0
            # 這裡也要用關鍵字參數
            return SignalEvent(
                type=EventType.SIGNAL,
                symbol="", 
                signal_type=SignalType.FLATTEN, 
                reason=f"STOP LOSS triggered (-{self.stop_loss:.0f} pts)"
            )
        return None

    def on_tick(self, tick: TickEvent) -> SignalEvent:
        return None