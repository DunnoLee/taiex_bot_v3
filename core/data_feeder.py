from abc import ABC, abstractmethod
from typing import Callable, Optional
from core.event import TickEvent, BarEvent

class DataFeeder(ABC):
    """
    數據餵食器的抽象基類。
    不管是接 Shioaji 還是讀 CSV，都必須遵守這個介面。
    """
    
    def __init__(self):
        self.on_tick_callback: Optional[Callable[[TickEvent], None]] = None
        self.on_bar_callback: Optional[Callable[[BarEvent], None]] = None

    def set_on_tick(self, callback: Callable[[TickEvent], None]):
        """註冊當有新 Tick 進來時要通知誰 (通常是 Strategy)"""
        self.on_tick_callback = callback

    def set_on_bar(self, callback: Callable[[BarEvent], None]):
        """註冊當有新 Bar 完成時要通知誰"""
        self.on_bar_callback = callback

    @abstractmethod
    def connect(self):
        """連線 (Shioaji 登入 / CSV 開檔)"""
        pass

    @abstractmethod
    def subscribe(self, symbol: str):
        """訂閱商品"""
        pass

    @abstractmethod
    def start(self):
        """開始推送數據"""
        pass

    @abstractmethod
    def stop(self):
        """停止推送"""
        pass