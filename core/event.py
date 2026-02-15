from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class EventType(Enum):
    """定義系統內的事件類型"""
    TICK = "TICK"
    BAR = "BAR"           # K線完成事件
    SIGNAL = "SIGNAL"     # 策略發出的買賣訊號
    ORDER = "ORDER"       # 執行層發出的委託單
    FILL = "FILL"         # 成交回報
    ERROR = "ERROR"       # 錯誤訊息

@dataclass
class Event:
    """所有事件的基礎類別"""
    type: EventType
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class TickEvent(Event):
    """即時報價事件"""
    type: EventType = EventType.TICK
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    bid_price: float = 0.0
    ask_price: float = 0.0

@dataclass
class BarEvent(Event):
    """K線 (1分K/5分K) 事件"""
    type: EventType = EventType.BAR
    symbol: str = ""
    period: str = "1m"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

class SignalType(Enum):
    LONG = "LONG"     # 做多
    SHORT = "SHORT"   # 做空
    FLATTEN = "FLATTEN" # 平倉 / 空手

@dataclass
class SignalEvent(Event):
    """策略計算後發出的訊號"""
    type: EventType = EventType.SIGNAL
    symbol: str = ""
    signal_type: SignalType = SignalType.FLATTEN
    strength: float = 1.0  # 訊號強度 (預留給未來資金管理用)
    reason: str = ""       # 訊號理由 (例如: "MA Cross Up")