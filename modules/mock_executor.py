from core.execution import ExecutionHandler
from core.event import SignalEvent, FillEvent, SignalType
from config.settings import Settings

class MockExecutor(ExecutionHandler):
    def __init__(self, initial_capital: float = 500000):
        self.capital = initial_capital
        self.current_position = 0 
        self.avg_price = 0.0 
        
        self.trades = []
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0

    def execute_signal(self, signal: SignalEvent, price: float) -> str:
        if not signal: return ""
        
        trade_action = ""
        pnl = 0.0
        
        # 為了避免 Enum 比對問題，我們轉成字串來判斷，最穩健
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
        #print(f"sig_type:{sig_type}")
        # --- 1. 平倉邏輯 ---
        # 多單平倉 (收到 SHORT 或 FLATTEN)
        if self.current_position > 0 and sig_type in ["SHORT", "FLATTEN"]:
            point_value = 10 # 微台一點10元
            pnl = (price - self.avg_price) * abs(self.current_position) * point_value
            self._record_trade(pnl)
            trade_action = f"📉 平多單 (獲利: ${pnl:.0f})"
            self.current_position = 0

        # 空單平倉 (收到 LONG 或 FLATTEN)
        elif self.current_position < 0 and sig_type in ["LONG", "FLATTEN"]:
            point_value = 10
            pnl = (self.avg_price - price) * abs(self.current_position) * point_value
            self._record_trade(pnl)
            trade_action = f"📈 平空單 (獲利: ${pnl:.0f})"
            self.current_position = 0

        # --- 2. 開倉邏輯 ---
        # 如果經過上面的平倉後，現在是空手 (0)，才能開新倉
        if self.current_position == 0:
            if sig_type == "LONG":
                self.current_position = 1
                self.avg_price = price
                trade_action = f"🔴 做多 @ {price}" if not trade_action else f"{trade_action} -> 🔴 反手做多"
            
            elif sig_type == "SHORT":
                self.current_position = -1
                self.avg_price = price
                trade_action = f"🟢 做空 @ {price}" if not trade_action else f"{trade_action} -> 🟢 反手做空"

        #print(signal.symbol)
        return trade_action

    def _record_trade(self, pnl):
        self.total_pnl += pnl
        self.trades.append(pnl)
        if pnl > 0: self.win_count += 1
        else: self.loss_count += 1

    def print_report(self):
        total_trades = len(self.trades)
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        print("\n" + "="*40)
        print(f"📊 模擬交易績效報告 (Mock Replay)")
        print("="*40)
        print(f"💰 總損益: ${self.total_pnl:,.0f} TWD")
        print(f"🔢 總交易次數: {total_trades}")
        print(f"🏆 勝率: {win_rate:.1f}%")
        print("="*40 + "\n")