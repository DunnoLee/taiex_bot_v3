import shioaji as sj
from datetime import datetime
from core.data_feeder import DataFeeder
from core.event import TickEvent
from config.settings import Settings

class ShioajiFeeder(DataFeeder):
    def __init__(self):
        super().__init__()
        self.api = sj.Shioaji()
        self.target_code = ""

    def connect(self):
        print("🔌 [Shioaji] 正在連線...")
        self.api.login(Settings.API_KEY, Settings.API_SECRET)
        print(f"✅ 登入成功: {Settings.ACC_ID}")

        # 設定 Callback
        self.api.quote.set_on_tick_fop_v1_callback(self._on_tick_received)

    def subscribe(self, symbol: str):
        # 1. 取得類別 (例如 TMF)
        target_category = symbol or Settings.SYMBOL_CODE
        print(f"🔍 [Shioaji] 正在搜尋合約類別: {target_category}...")
        
        # 使用 .get() 安全存取，避免當機
        contracts = self.api.Contracts.Futures.get(target_category)
        
        if not contracts:
            print(f"❌ 找不到類別 '{target_category}' 的合約。")
            print("💡 提示: 請確認 API 帳號權限或合約代碼 (如 MXF, TMF, TXF)")
            return

        # 2. 篩選邏輯 (更穩健的版本)
        # 我們不要限制長度，改為排除「跨月價差單」
        # 通常一般合約的 delivery_month 會有值，且 code 不會包含複雜的價差標記
        normal_contracts = []
        for c in contracts:
            # 排除選擇權或非目標商品 (雖然 Futures[cat] 應該很乾淨，但檢查一下)
            if not c.code.startswith(target_category): continue
            
            # 排除價差單 (Spread): 通常 delivery_month 會有特殊的標記，或者我們只取 code 單純的
            # 最簡單的方法：只取 delivery_month 是數字的 (例如 '202603')
            if c.delivery_month and c.delivery_month.isdigit():
                normal_contracts.append(c)

        if not normal_contracts:
            print(f"❌ 篩選後無合約 (原始數量: {len(contracts)})")
            return

        # 3. 排序並取最近月 (Front Month)
        # 依照交割月排序 (例如 '202603' < '202604')
        sorted_contracts = sorted(normal_contracts, key=lambda x: x.delivery_month)
        target = sorted_contracts[0]
        
        self.target_code = target.code
        print(f"🎯 鎖定合約: {target.name} ({self.target_code}) 交割月: {target.delivery_month}")
        
        # 4. 訂閱
        self.api.quote.subscribe(target, quote_type=sj.constant.QuoteType.Tick, version=sj.constant.QuoteVersion.v1)
        print(f"✅ 已送出訂閱請求")

    def start(self):
        print("🚀 [Shioaji] 實盤監聽中... (按 Ctrl+C 停止)")
        pass

    def stop(self):
        self.api.logout()
        print("👋 斷線")

    def _on_tick_received(self, exchange, tick):
        """處理 Shioaji 傳回來的 Tick"""
        # 注意: 如果訂閱到非即時行情，Shioaji 有時回傳的 tick.close 會是 int 或 decimal
        event = TickEvent(
            symbol=self.target_code,
            price=float(tick.close),
            volume=int(tick.volume),
            timestamp=datetime.now(),
            simulated=False
        )
        
        if self.on_tick_callback:
            self.on_tick_callback(event)