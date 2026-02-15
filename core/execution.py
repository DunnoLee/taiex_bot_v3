from abc import ABC, abstractmethod
from typing import Optional
from core.event import OrderEvent, FillEvent, SignalEvent

class ExecutionHandler(ABC):
    """
    執行層抽象基類。
    負責接收 Signal (訊號) -> 轉換為 Order (委託) -> 回報 Fill (成交)。
    """
    
    @abstractmethod
    def execute_signal(self, signal: SignalEvent) -> Optional[FillEvent]:
        """
        處理策略發出的訊號，並回傳成交結果 (如果是模擬)。
        實盤模式下，這裡可能會是非同步操作，不直接回傳 Fill。
        """
        pass