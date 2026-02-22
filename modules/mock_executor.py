from core.base_executor import BaseExecutor
import time

# 建立一個假的期交所回報物件 (模仿 Shioaji 的格式)
class MockUpdateInfo:
    def __init__(self, status="Filled"):
        self.status = status

class MockExecutor(BaseExecutor):
    """
    模擬執行器 (搭載真實滑價模擬系統)
    收到命令 -> 疊加滑價懲罰 -> 回傳 '成交'
    """
    def __init__(self, initial_capital=500000, slippage_points=1.0):
        super().__init__(initial_capital)
        # 🚀 新增：預設每次成交滑價 1 點 (進出各滑 1 點，一趟就是 2 點成本)
        self.slippage_points = slippage_points 
        self.order_callback = None  # 🚀 新增：用來存放回報機制的電話號碼

    def set_order_callback(self, callback):
        """模擬 Shioaji 的 api.set_order_callback"""
        self.order_callback = callback

    def _execute_impl(self, direction, qty, price):
        fill_price = price 
        if direction.upper() == 'BUY': fill_price = price + self.slippage_points
        elif direction.upper() == 'SELL': fill_price = price - self.slippage_points
            
        msg = f"⚡️ [Mock] {direction} {qty} @ {fill_price:.2f} (滑價:{self.slippage_points})"
        print(msg) # 🚀 確保終端機能印出這行，讓儀表板抓到！
        
        # 🚀 模擬期交所的「非同步延遲回報」
        if self.order_callback:
            def fire_callback():
                time.sleep(0.5) # 假裝網路傳輸花了 0.5 秒
                mock_info = MockUpdateInfo(status="Filled")
                self.order_callback(mock_info, None)
                
            # 開啟背景執行緒去打電話，不卡住目前的帳本結算！
            import threading
            threading.Thread(target=fire_callback, daemon=True).start()
            
        return True, fill_price, msg