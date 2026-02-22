from core.base_executor import BaseExecutor

class MockExecutor(BaseExecutor):
    """
    模擬執行器 (搭載真實滑價模擬系統)
    收到命令 -> 疊加滑價懲罰 -> 回傳 '成交'
    """
    def __init__(self, initial_capital=500000, slippage_points=1.0):
        super().__init__(initial_capital)
        # 🚀 新增：預設每次成交滑價 1 點 (進出各滑 1 點，一趟就是 2 點成本)
        self.slippage_points = slippage_points 

    def _execute_impl(self, direction, qty, price):
        """
        實作: 假裝成交，並模擬真實市場的吃虧滑價
        """
        fill_price = price 
        
        # === 🩸 殘酷滑價模擬器 ===
        # 確保 direction 轉成大寫來比對
        if direction.upper() == 'BUY':
            # 買進時，市場不給你原本的報價，強迫你買得「更貴」
            fill_price = price + self.slippage_points
            
        elif direction.upper() == 'SELL':
            # 賣出時，市場沒人接刀子，強迫你賣得「更便宜」
            fill_price = price - self.slippage_points
            
        # 在訊息中記錄真實成交價與原本觸發價的差異，方便你對帳
        msg = f"[Mock] {direction} {qty} @ {fill_price:.2f} (觸發價:{price:.2f}, 滑價吃虧:{self.slippage_points}點)"
        
        return True, fill_price, msg