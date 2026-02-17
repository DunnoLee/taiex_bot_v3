from core.base_executor import BaseExecutor

class RealExecutor(BaseExecutor):
    def __init__(self, api, account):
        super().__init__()
        self.api = api
        self.account = account

    def _execute_impl(self, direction, qty, price):
        """
        [實作] 真實下單
        """
        # 1. 轉換參數給 Shioaji
        action = self.api.Constants.Action.Buy if direction == "BUY" else self.api.Constants.Action.Sell
        price_type = self.api.Constants.PriceType.Limit # 或 Market
        
        # 2. 送出訂單
        contract = self.api.Contracts.Futures.TMF[self.month]
        order = self.api.Order(
            action=action,
            price=price,
            quantity=qty,
            order_type=price_type,
            price_type=self.api.Constants.StockPriceType.Limit
        )
        
        trade = self.api.place_order(contract, order)
        
        # 3. 等待成交回報 (這裡可能要用 callback 機制，比較複雜，暫示範同步)
        # 假設成交了
        fill_price = price # 實際上要從 trade.status 拿
        msg = f"API 下單成功: {trade.order.id}"
        
        return True, fill_price, msg