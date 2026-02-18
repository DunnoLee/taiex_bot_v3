from core.base_executor import BaseExecutor

class MockExecutor(BaseExecutor):
    """
    模擬執行器
    只負責: 收到命令 -> 回傳 '成功' (不處理邏輯)
    """
    def __init__(self, initial_capital=500000):
        super().__init__(initial_capital)

    def _execute_impl(self, direction, qty, price):
        """
        實作: 假裝成交
        """
        # 在這裡可以加入滑價模擬 (Slippage)
        fill_price = price 
        msg = f"[Mock] {direction} {qty} @ {fill_price}"
        return True, fill_price, msg