from abc import ABC, abstractmethod
from typing import List, Optional
from core.event import BarEvent, TickEvent, SignalEvent, SignalType

class BaseStrategy(ABC):
    """
    策略抽象基類 (Abstract Base Class)。
    所有具體的策略 (如 MAStrategy) 都必須繼承此類別。
    """
    
    def __init__(self, name: str):
        self.name = name
        self.position: int = 0  # 策略認知的目前倉位 (多單為正，空單為負)
        self.active: bool = True # 策略開關
        
        # 這裡不放 API，只放數據容器
        # 例如: self.bars = []

    @abstractmethod
    def on_bar(self, bar: BarEvent) -> Optional[SignalEvent]:
        """
        當 K 線完成時觸發。
        回傳: SignalEvent (如果有訊號) 或 None
        """
        pass

    @abstractmethod
    def on_tick(self, tick: TickEvent) -> Optional[SignalEvent]:
        """
        當 Tick 進來時觸發 (例如用於觸價停損)。
        回傳: SignalEvent (如果有訊號) 或 None
        """
        pass

    def set_position(self, pos: int):
        """外部 (Commander) 強制修正策略倉位"""
        print(f"🔄 [Strategy] 倉位修正: {self.position} -> {pos}")
        self.position = pos