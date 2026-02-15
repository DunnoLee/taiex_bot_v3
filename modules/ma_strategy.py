import pandas as pd
import numpy as np
from collections import deque
from core.strategy import BaseStrategy
from core.event import BarEvent, TickEvent, SignalEvent, SignalType
from config.settings import Settings

class MAStrategy(BaseStrategy):
    """
    雙均線策略 (Dual Moving Average Cross)
    邏輯:
    1. 快線(Fast MA) 上穿 慢線(Slow MA) -> 做多 (Long)
    2. 快線(Fast MA) 下穿 慢線(Slow MA) -> 做空 (Short)
    """
    def __init__(self, fast_window: int = 10, slow_window: int = 60):
        super().__init__("MA_Cross_Strategy")
        
        # 從 Settings 讀取參數 (如果沒傳入的話)
        self.fast_window = fast_window or Settings.STRATEGY_MA_FAST
        self.slow_window = slow_window or Settings.STRATEGY_MA_SLOW
        
        # 歷史收盤價容器 (只存需要的長度，避免記憶體爆炸)
        # 為了計算 MA，我們至少需要 slow_window + 一些緩衝
        self.history_closes = deque(maxlen=self.slow_window + 10)
        
        print(f"🧠 [MAStrategy] 初始化完成 (Fast={self.fast_window}, Slow={self.slow_window})")

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        if not self.active: return None

        # 1. 儲存最新收盤價
        self.history_closes.append(bar.close)

        # 2. 檢查資料長度是否足夠計算 MA
        if len(self.history_closes) < self.slow_window:
            return None

        # 3. 計算 MA (使用 Pandas)
        closes = pd.Series(self.history_closes)
        ma_fast = closes.rolling(window=self.fast_window).mean().iloc[-1]
        ma_slow = closes.rolling(window=self.slow_window).mean().iloc[-1]
        
        # 取得前一根的 MA 值 (用於判斷交叉)
        prev_ma_fast = closes.rolling(window=self.fast_window).mean().iloc[-2]
        prev_ma_slow = closes.rolling(window=self.slow_window).mean().iloc[-2]

        # 4. 產生訊號邏輯 (黃金交叉 / 死亡交叉)
        signal = None
        
        # 黃金交叉 (快線向上穿過慢線)
        if prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow:
            # 只有當我們 "不是" 多單時才進場
            if self.position <= 0:
                signal = SignalEvent(
                    symbol=bar.symbol,
                    signal_type=SignalType.LONG,
                    reason=f"Golden Cross (Fast:{ma_fast:.1f} > Slow:{ma_slow:.1f})"
                )

        # 死亡交叉 (快線向下穿過慢線)
        elif prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow:
            # 只有當我們 "不是" 空單時才進場
            if self.position >= 0:
                signal = SignalEvent(
                    symbol=bar.symbol,
                    signal_type=SignalType.SHORT,
                    reason=f"Death Cross (Fast:{ma_fast:.1f} < Slow:{ma_slow:.1f})"
                )

        # 5. 回傳訊號 (如果有的話)
        if signal:
            print(f"💡 [Strategy Signal] {signal.signal_type} @ {bar.close} | Reason: {signal.reason}")
        
        return signal

    def on_tick(self, tick: TickEvent) -> SignalEvent:
        # MA 策略通常只看 K 棒收盤，這裡暫時不需要 Tick 級別的邏輯
        # 除非你要做 Tick 級別的硬止損 (未來可以加在這裡)
        return None