from core.event import SignalEvent, SignalType

class BaseExecutor:
    """
    執行器基底類別 (The Shared Brain)
    遵循原則: Main_Live 與 Main_Simulation 共用所有邏輯，
    只有「實際下單 (IO)」動作由子類別實作。
    """
    def __init__(self, initial_capital=500000):
        self.capital = initial_capital
        self.current_position = 0
        self.avg_price = 0.0
        
        # 交易紀錄 (影子帳本)
        self.trades = []
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        
        # TMF 規格 (微台)
        self.POINT_VALUE = 10.0
        self.FEE = 22.0

    def execute_signal(self, signal: SignalEvent, price: float) -> str:
        """
        統一對外的接口 (Engine 呼叫這個)
        負責: 解析訊號 -> 計算邏輯 -> 呼叫實作層 -> 更新帳本
        """
        if not signal: return ""

        # 1. 解析參數
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
        is_manual = "Manual" in str(signal.reason)
        qty = int(signal.strength) if signal.strength else 1

        trade_action = ""
        pnl = 0.0
        fee_total = 0.0

        # --- 2. 處理 FLATTEN (全平倉) ---
        if sig_type in ["FLATTEN", "FLATTEN_LONG", "FLATTEN_SHORT"]:
            if self.current_position != 0:
                direction = "SELL" if self.current_position > 0 else "BUY"
                close_qty = abs(self.current_position)
                
                # 呼叫子類別執行 (真實下單或模擬)
                success, fill_price, msg = self._execute_impl(direction, close_qty, price)
                if not success: return f"❌ 平倉失敗: {msg}"

                # 更新帳本
                pnl = self._calculate_pnl(self.current_position, fill_price, close_qty)
                fee_total = self.FEE * close_qty
                final_pnl = pnl - fee_total
                
                self._record_trade(final_pnl)
                trade_action = f"📉 全平倉 (獲利: ${final_pnl:.0f})"
                
                # 清空狀態
                self.current_position = 0
                self.avg_price = 0.0
                return trade_action
            return ""

        # --- 3. 處理 LONG/SHORT ---
        action_dir = 0 # 1=Buy, -1=Sell
        if sig_type == "LONG": action_dir = 1
        elif sig_type == "SHORT": action_dir = -1
        
        if action_dir == 0: return ""
        direction_str = "BUY" if action_dir == 1 else "SELL"

        # 邏輯 A: 同向加碼 (Pyramiding)
        if (self.current_position > 0 and action_dir == 1) or \
           (self.current_position < 0 and action_dir == -1):
            
            if is_manual: # 只有手動允許可加碼
                # 執行交易
                success, fill_price, msg = self._execute_impl(direction_str, qty, price)
                if not success: return f"❌ 加碼失敗: {msg}"

                # 更新平均成本 (加權平均)
                old_val = abs(self.current_position) * self.avg_price
                new_val = qty * fill_price
                total_qty = abs(self.current_position) + qty
                self.avg_price = (old_val + new_val) / total_qty
                
                self.current_position += (action_dir * qty)
                self.total_pnl -= (self.FEE * qty) # 扣手續費
                
                trade_action = f"{'🔴' if action_dir==1 else '🟢'} 加碼 {qty} 口 (均價: {self.avg_price:.0f})"

        # 邏輯 B: 反向 (平倉 + 反手)
        elif (self.current_position > 0 and action_dir == -1) or \
             (self.current_position < 0 and action_dir == 1):
            
            # 1. 先平倉
            cover_qty = abs(self.current_position)
            
            # 這裡簡化：送出兩筆單 (平倉單 + 新單) 或一筆反手單
            # 為求精準，我們拆成兩步更新帳本
            
            # Step 1: 平倉交易
            close_dir = "SELL" if self.current_position > 0 else "BUY"
            success1, fill_price1, msg1 = self._execute_impl(close_dir, cover_qty, price)
            
            pnl = self._calculate_pnl(self.current_position, fill_price1, cover_qty)
            
            # Step 2: 開新倉 (反手)
            target_qty = qty if is_manual else 1
            success2, fill_price2, msg2 = self._execute_impl(direction_str, target_qty, price)
            
            # 結算
            fee_total = (self.FEE * cover_qty) + (self.FEE * target_qty)
            final_pnl = pnl - fee_total
            self._record_trade(final_pnl)
            
            self.current_position = action_dir * target_qty
            self.avg_price = fill_price2
            
            trade_action = f"📉 平倉損益 ${pnl:.0f} -> {'🔴' if action_dir==1 else '🟢'} 反手開倉"

        # 邏輯 C: 空手開倉
        elif self.current_position == 0:
            success, fill_price, msg = self._execute_impl(direction_str, qty, price)
            if success:
                self.current_position = action_dir * qty
                self.avg_price = fill_price
                self.total_pnl -= (self.FEE * qty)
                trade_action = f"{'🔴' if action_dir==1 else '🟢'} 新倉 {qty} 口 @ {fill_price}"

        return trade_action

    def _calculate_pnl(self, position, current_price, qty):
        """計算價差損益"""
        if position > 0: diff = current_price - self.avg_price
        else: diff = self.avg_price - current_price
        return diff * qty * self.POINT_VALUE

    def _record_trade(self, pnl):
        self.total_pnl += pnl
        self.trades.append(pnl)
        if pnl > 0: self.win_count += 1
        else: self.loss_count += 1

    def _execute_impl(self, direction, qty, price):
        """
        [抽象方法] 唯一的不同點
        子類別必須實作這一個方法
        回傳: (success: bool, fill_price: float, msg: str)
        """
        raise NotImplementedError
    
    # 維持你的報告功能
    def print_report(self):
        total_trades = len(self.trades)
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        print(f"💰 總損益: ${self.total_pnl:,.0f} | 勝率: {win_rate:.1f}%")