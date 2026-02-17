# core/base_executor.py

class BaseExecutor:
    """
    執行器基底類別 (Shadow Ledger)
    負責: 本地倉位追蹤、平均成本計算、損益試算 (Mock/Real 共用)
    """
    def __init__(self, initial_capital=500000):
        self.capital = initial_capital
        self.current_position = 0
        self.avg_price = 0.0
        
        self.total_pnl = 0.0
        self.trades = []
        self.win_count = 0
        self.loss_count = 0
        
        # 規格設定
        self.POINT_VALUE = 10.0  # 微台
        self.FEE = 22.0          # 單邊手續費

    def order(self, direction: str, qty: int, price: float, reason: str = "") -> str:
        """
        統一對外的下單接口 (Engine 只呼叫這個)
        direction: "BUY" or "SELL"
        """
        # 1. 呼叫子類別的實際下單功能 (Mock 或 Real)
        # 如果是 Real，這裡會真的送單到交易所
        # 如果是 Mock，這裡直接回傳 True
        success, fill_price, msg = self._execute_impl(direction, qty, price)
        
        if not success:
            return f"❌ 下單失敗: {msg}"

        # 2. 如果成交了，更新本地的「影子帳本」 (Mock/Real 通用邏輯)
        self._update_ledger(direction, qty, fill_price)
        
        return f"{msg} (倉位: {self.current_position}, 均價: {self.avg_price:.0f})"

    def _execute_impl(self, direction, qty, price):
        """
        [抽象方法] 實際執行交易
        由 MockExecutor 和 RealExecutor 分別實作
        """
        raise NotImplementedError("子類別必須實作 _execute_impl")

    def _update_ledger(self, direction, qty, price):
        """
        核心邏輯：更新倉位、計算成本與損益
        (這就是你原本寫在 Mock 裡的那一大段邏輯)
        """
        # 判斷是「新倉/加碼」還是「平倉」
        is_closing = False
        
        if direction == "BUY" and self.current_position < 0: is_closing = True
        elif direction == "SELL" and self.current_position > 0: is_closing = True
        
        trade_pnl = 0.0
        
        if is_closing:
            # 平倉邏輯
            cover_qty = min(qty, abs(self.current_position)) # 能平掉幾口
            
            if self.current_position > 0: # 多單平倉
                diff = price - self.avg_price
            else: # 空單平倉
                diff = self.avg_price - price
            
            trade_pnl = diff * cover_qty * self.POINT_VALUE
            
            # 更新剩餘倉位
            if direction == "BUY": self.current_position += cover_qty
            else: self.current_position -= cover_qty
            
            # 如果平光了，成本歸零
            if self.current_position == 0: self.avg_price = 0.0
            
            # 如果還有剩 (翻單)，剩下的 qty 變成新倉
            remain_qty = qty - cover_qty
            if remain_qty > 0:
                self._open_position(direction, remain_qty, price)

        else:
            # 新倉或加碼邏輯
            self._open_position(direction, qty, price)

        # 扣除手續費 (總口數)
        fee_total = self.FEE * qty
        final_pnl = trade_pnl - fee_total
        
        # 記錄
        self.total_pnl += final_pnl
        if trade_pnl != 0: # 只有平倉才算輸贏
            self.trades.append(final_pnl)
            if final_pnl > 0: self.win_count += 1
            else: self.loss_count += 1

    def _open_position(self, direction, qty, price):
        """加碼或開新倉的成本計算"""
        if self.current_position == 0:
            self.avg_price = price
            self.current_position = qty if direction == "BUY" else -qty
        else:
            # 加碼：計算加權平均
            old_value = abs(self.current_position) * self.avg_price
            new_value = qty * price
            total_qty = abs(self.current_position) + qty
            self.avg_price = new_value + old_value / total_qty # 修正算法: (old+new)/total
            self.avg_price = (old_value + new_value) / total_qty # 這樣才對
            
            if direction == "BUY": self.current_position += qty
            else: self.current_position -= qty