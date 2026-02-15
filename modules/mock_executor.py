from core.execution import ExecutionHandler
from core.event import SignalEvent, FillEvent, SignalType, OrderType
from config.settings import Settings

class MockExecutor(ExecutionHandler):
    """
    模擬交易所與帳戶。
    功能：
    1. 接收訊號並模擬成交 (假設無滑價，以收盤價成交)。
    2. 計算交易損益 (PnL)。
    3. 統計勝率與總交易次數。
    """
    def __init__(self, initial_capital: float = 500000):
        self.capital = initial_capital  # 初始資金
        self.current_position = 0       # 目前倉位
        self.avg_price = 0.0            # 建倉均價
        
        # 統計數據
        self.trades = []      # 紀錄每一筆平倉損益
        self.total_pnl = 0.0  # 累計損益
        self.win_count = 0    # 勝場數
        self.loss_count = 0   # 敗場數

        print(f"💰 [MockExecutor] 帳戶初始化: ${self.capital:,.0f}")

    def execute_signal(self, signal: SignalEvent, price: float) -> str:
        """
        模擬執行訊號。
        注意：這裡需要傳入當前價格 (price)，因為 Mock 模式下我們知道價格。
        回傳: 執行結果的文字描述 (用於 Log)
        """
        if not signal: return ""

        trade_action = ""
        pnl = 0.0
        
        # --- 1. 處理平倉邏輯 (如果方向相反或要求平倉) ---
        # 如果目前有多單，且訊號是做空或平倉 -> 賣出平倉
        if self.current_position > 0 and signal.signal_type in [SignalType.SHORT, SignalType.FLATTEN]:
            pnl = (price - self.avg_price) * abs(self.current_position) * 200  # 小台一點 50元 (這裡假設微台 x10? 還是小台 x50? 先假設微台 TMF x 50 好了，請依實際調整)
            # 微台 TMF 跳動一點是 10 元 TWD? 還是 50? 
            # 假設是微台指 (TMF) = 10 TWD / 點 (如果是小台是 50)
            # 這裡我們先用變數，你之後可以在 Settings 設定
            point_value = 10 
            pnl = (price - self.avg_price) * abs(self.current_position) * point_value
            
            self._record_trade(pnl)
            trade_action = f"📉 平多單 (獲利: ${pnl:.0f})"
            self.current_position = 0

        # 如果目前有空單，且訊號是做多或平倉 -> 買進平倉
        elif self.current_position < 0 and signal.signal_type in [SignalType.LONG, SignalType.FLATTEN]:
            point_value = 10
            pnl = (self.avg_price - price) * abs(self.current_position) * point_value
            
            self._record_trade(pnl)
            trade_action = f"📈 平空單 (獲利: ${pnl:.0f})"
            self.current_position = 0

        # --- 2. 處理進場邏輯 (如果是開倉) ---
        if signal.signal_type == SignalType.LONG and self.current_position == 0:
            self.current_position = 1
            self.avg_price = price
            trade_action = f"🔴在此買進做多 @ {price}"
            
        elif signal.signal_type == SignalType.SHORT and self.current_position == 0:
            self.current_position = -1
            self.avg_price = price
            trade_action = f"🟢在此賣出做空 @ {price}"

        return trade_action

    def _record_trade(self, pnl):
        self.total_pnl += pnl
        self.trades.append(pnl)
        if pnl > 0: self.win_count += 1
        else: self.loss_count += 1

    def print_report(self):
        """印出最終績效報告"""
        total_trades = len(self.trades)
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        
        print("\n" + "="*40)
        print(f"📊 模擬交易績效報告 (Mock Replay)")
        print("="*40)
        print(f"💰 總損益: ${self.total_pnl:,.0f} TWD")
        print(f"🔢 總交易次數: {total_trades}")
        print(f"🏆 勝率: {win_rate:.1f}% ({self.win_count}勝 {self.loss_count}敗)")
        print(f"📈 最終倉位: {self.current_position} 口")
        print("="*40 + "\n")