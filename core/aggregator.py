from datetime import datetime, timedelta
from typing import Callable, Optional
from core.event import TickEvent, BarEvent

class BarAggregator:
    """
    K 線合成器 (The Translator)。
    職責: 接收 Tick -> 累積 -> 每分鐘切換時吐出 BarEvent。
    """
    def __init__(self, symbol: str, interval_minutes: int = 1):
        self.symbol = symbol
        self.interval = interval_minutes
        
        # 暫存區
        self.current_bar: Optional[BarEvent] = None
        self.on_bar_callback: Optional[Callable[[BarEvent], None]] = None
        
        print(f"🔧 [Aggregator] 啟動 K 線合成 ({self.interval}分K)")

    def set_on_bar(self, callback: Callable[[BarEvent], None]):
        self.on_bar_callback = callback

    def on_tick(self, tick: TickEvent):
        """
        處理每一筆進來的 Tick。
        """
        # 忽略模擬的 Tick (如果有的話) 或者非目標商品的 Tick
        if tick.symbol != self.symbol: return

        # 判斷 Tick 所屬的分鐘 (去掉秒數)
        tick_time = tick.timestamp.replace(second=0, microsecond=0)
        
        # --- 初始化第一根 K 棒 ---
        if self.current_bar is None:
            self._create_new_bar(tick, tick_time)
            return

        # --- 判斷是否換分 (新的一分鐘開始) ---
        # 如果 Tick 時間 > 目前 Bar 的時間，代表上一根 Bar 完成了
        if tick_time > self.current_bar.timestamp:
            # 1. 完成上一根 Bar -> 推送
            self._finish_current_bar()
            
            # 2. 建立新的一根 Bar
            self._create_new_bar(tick, tick_time)
        else:
            # --- 同一分鐘內，更新 High/Low/Close/Volume ---
            self._update_current_bar(tick)

    def _create_new_bar(self, tick: TickEvent, timestamp: datetime):
        self.current_bar = BarEvent(
            symbol=self.symbol,
            period=f"{self.interval}m",
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.volume,
            timestamp=timestamp
        )

    def _update_current_bar(self, tick: TickEvent):
        if not self.current_bar: return
        
        # 更新最高/最低價
        self.current_bar.high = max(self.current_bar.high, tick.price)
        self.current_bar.low = min(self.current_bar.low, tick.price)
        
        # 更新收盤價與成交量
        self.current_bar.close = tick.price
        self.current_bar.volume += tick.volume

    def _finish_current_bar(self):
        """推送完成的 K 棒"""
        if self.current_bar and self.on_bar_callback:
            # 這裡可以做一個 copy，避免被後續修改
            # 但為了效能，我們直接送出
            # print(f"🔨 [Aggregator] 完成 K 棒: {self.current_bar.timestamp} C={self.current_bar.close}")
            self.on_bar_callback(self.current_bar)