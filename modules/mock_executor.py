from core.base_executor import BaseExecutor
from core.event import SignalEvent, SignalType

class MockExecutor(BaseExecutor):
    """
    模擬執行器 (只負責 '假裝成交')
    """
    def __init__(self, initial_capital=500000):
        super().__init__(initial_capital)

    def execute_signal(self, signal: SignalEvent, price: float) -> str:
        """
        解析訊號並轉換為 order() 呼叫
        (這是為了相容 Engine 目前的呼叫方式)
        """
        # 這裡的邏輯是: 把策略的 Signal 翻譯成 BUY/SELL 指令
        # 真正計算倉位的邏輯已經移到 BaseExecutor._update_ledger 了
        
        # 解析方向
        direction = ""
        qty = int(signal.strength) if signal.strength else 1
        is_manual = "Manual" in str(signal.reason)

        # 簡單化：Mock 直接相信訊號
        # 注意：Engine 已經做了 Smart Logic (Flatten 會轉成 Buy/Sell)
        # 所以這裡只要單純翻譯就好
        
        if signal.signal_type == SignalType.LONG: direction = "BUY"
        elif signal.signal_type == SignalType.SHORT: direction = "SELL"
        
        # 處理平倉訊號 (Flatten) -> Engine 雖然有轉，但如果是策略發出的 FLATTEN 也要處理
        elif "FLATTEN" in str(signal.signal_type):
             if self.current_position > 0: direction = "SELL"; qty = abs(self.current_position)
             elif self.current_position < 0: direction = "BUY"; qty = abs(self.current_position)
             else: return None # 已空手

        if not direction: return None

        # 呼叫老爸的標準下單接口
        return self.order(direction, qty, price, signal.reason)

    def _execute_impl(self, direction, qty, price):
        """
        [實作] 模擬成交
        在真實世界這裡要 call API，這裡直接 return True
        """
        # 模擬滑價? 這裡先不加
        fill_price = price 
        msg = f"{'🔴' if direction=='BUY' else '🟢'} {direction} {qty} @ {fill_price}"
        return True, fill_price, msg