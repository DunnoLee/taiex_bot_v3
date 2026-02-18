from abc import ABC, abstractmethod
from core.event import OrderEvent, FillEvent, SignalEvent

class BaseStrategy(ABC):
    """
    策略基底類別 (通用卡帶插槽)
    所有策略都必須繼承這個類別，並實作 on_bar 方法。
    """
    def __init__(self, name="Unknown Strategy"):
        self.name = name
        self.position = 0         # 策略建議的倉位
        self.entry_price = 0.0    # 進場價
        self.raw_bars = []        # K棒紀錄

    @abstractmethod
    def on_bar(self, bar) -> 'SignalEvent':
        """
        核心邏輯：每根 K 棒進來時，策略要決定做什麼
        (子類別必須實作這個方法)
        """
        pass

    def load_history_bars(self, bars):
        """通用功能：載入歷史 K 棒"""
        self.raw_bars = bars
        print(f"[{self.name}] 已載入 {len(bars)} 根歷史數據")

    def set_position(self, pos):
        """通用功能：更新倉位"""
        self.position = pos