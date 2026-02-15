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

# --- 資料事件 ---
@dataclass
class TickEvent(Event):
    type: EventType = EventType.TICK
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    bid_price: float = 0.0
    ask_price: float = 0.0
    simulated: bool = False

@dataclass
class BarEvent(Event):
    type: EventType = EventType.BAR
    symbol: str = ""
    period: str = "1m"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    interval: str = "1m"

# --- 交易相關 Enum ---
class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLATTEN = "FLATTEN"

class OrderType(Enum):
    MARKET = "MARKET" # 市價單
    LIMIT = "LIMIT"   # 限價單

class OrderDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"

# --- 訊號與交易事件 ---
@dataclass
class SignalEvent(Event):
    """策略發出的訊號"""
    type: EventType = EventType.SIGNAL
    symbol: str = ""
    signal_type: SignalType = SignalType.FLATTEN
    strength: float = 1.0
    reason: str = ""

@dataclass
class OrderEvent(Event):
    """執行層發出的委託單 (準備送去券商)"""
    type: EventType = EventType.ORDER
    symbol: str = ""
    order_type: OrderType = OrderType.MARKET
    direction: OrderDirection = OrderDirection.BUY
    quantity: int = 1
    price: float = 0.0 # 限價單才需要，市價單為 0

@dataclass
class FillEvent(Event):
    """券商回報的成交明細"""
    type: EventType = EventType.FILL
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0 # 手續費
    exchange: str = "TAIFEX"