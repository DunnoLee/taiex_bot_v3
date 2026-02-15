from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class EventType(Enum):
    TICK = "TICK"
    BAR = "BAR"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"
    ERROR = "ERROR"

@dataclass
class Event:
    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class TickEvent(Event):
    """
    統一的 Tick 格式。
    來源可能是: Shioaji Realtime Quote 或 Historical CSV playback
    """
    type: EventType = EventType.TICK
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    bid_price: float = 0.0  # 委買價 (用於模擬成交)
    ask_price: float = 0.0  # 委賣價
    simulated: bool = False # 標記是否為模擬數據

@dataclass
class BarEvent(Event):
    """
    統一的 K 線格式 (1分K/5分K)。
    """
    type: EventType = EventType.BAR
    symbol: str = ""
    period: str = "1m"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    interval: str = "1m" # 1m, 5m, 15m...

# --- 下面是這次新增的 ---

class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLATTEN = "FLATTEN"

@dataclass
class SignalEvent(Event):
    """策略發出的訊號"""
    type: EventType = EventType.SIGNAL
    symbol: str = ""
    signal_type: SignalType = SignalType.FLATTEN
    strength: float = 1.0
    reason: str = ""