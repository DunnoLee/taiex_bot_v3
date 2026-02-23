from core.base_executor import BaseExecutor
from config.settings import Settings
import shioaji as sj
from shioaji import constant, account # 引入 constant 用於判斷下單類型
import sys
import os

class RealExecutor(BaseExecutor):
    """
    真實執行器 (Shioaji API) - V3.7 實戰融合版
    特色:
    1. 自動掃描期貨帳號 (不再依賴外部傳入)
    2. 支援 CA 憑證自動啟動
    3. 精準下單參數: 市價(MKT)+IOC / 限價(LMT)+ROD
    4. 數值強制轉型 (Decimal -> Float/Int)
    """
    def __init__(self, api, dry_run=False):
        # 注意: 我們不再需要從外部傳入 account，因為我們會自己掃描
        super().__init__()
        self.api = api
        self.dry_run = dry_run
        self.contract = None 
        self.account = None

        # ---------------------------------------------------------
        # 1. 帳號掃描 (來自舊版 Trader)
        # ---------------------------------------------------------
        print("💳 [RealExecutor] 正在掃描可用期貨帳號...")
        try:
            all_accounts = self.api.list_accounts()
            for acc in all_accounts:
                if isinstance(acc, account.FutureAccount):
                    self.account = acc
                    break
            
            if self.account:
                print(f"✅ [RealExecutor] 成功綁定期貨帳號: {self.account.account_id}")
            else:
                print(f"❌ [RealExecutor] 嚴重警告：找不到任何期貨帳號！(將嘗試使用預設)")
                if self.api.stock_account:
                    self.account = self.api.stock_account

        except Exception as e:
            print(f"❌ [RealExecutor] 帳號掃描失敗: {e}")

        # ---------------------------------------------------------
        # 2. CA 憑證啟動 (V3 安全機制)
        # ---------------------------------------------------------
        if not self.dry_run:
            print("📜 [RealExecutor] 檢測為實戰模式，正在啟動 CA 憑證...")
            
            if not os.path.exists(Settings.SHIOAJI_CERT_PATH):
                print(f"❌ [RealExecutor] 找不到憑證檔案: {Settings.SHIOAJI_CERT_PATH}")
                sys.exit(1)

            try:
                self.api.activate_ca(
                    ca_path=Settings.SHIOAJI_CERT_PATH,
                    ca_passwd=Settings.SHIOAJI_CERT_PASSWORD,
                    person_id=Settings.SHIOAJI_PERSON_ID
                )
                print("✅ [RealExecutor] 憑證啟動成功！已取得下單權限。")
            except Exception as e:
                print(f"❌ [RealExecutor] 憑證啟動失敗: {e}")
                sys.exit(1)
        else:
            print("🛡️ [RealExecutor] Dry Run 模式：跳過憑證載入")

    def _resolve_shioaji_code(self, target_str):
        # (合約翻譯邏輯保持不變)
        try:
            if len(target_str) < 9: return target_str
            symbol = target_str[:3]
            year_str = target_str[3:7]
            month_str = target_str[7:]
            month_map = {"01":"A", "02":"B", "03":"C", "04":"D", "05":"E", "06":"F", "07":"G", "08":"H", "09":"I", "10":"J", "11":"K", "12":"L"}
            month_code = month_map.get(month_str)
            year_code = year_str[-1]
            if not month_code: raise ValueError(f"無效月份: {month_str}")
            return f"{symbol}{month_code}{year_code}"
        except: return target_str

    def _get_contract(self):
        # (取得合約邏輯保持不變)
        if self.contract is None:
            try:
                target_setting = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
                code = self._resolve_shioaji_code(target_setting)
                self.contract = self.api.Contracts.Futures.TMF[code]
                print(f"📄 [RealExecutor] 鎖定合約: {self.contract.name} ({self.contract.code})")
            except Exception as e:
                print(f"❌ [RealExecutor] 取得合約失敗: {e}")
        return self.contract

    def _execute_impl(self, direction, qty, price):
        """
        [實作] 真實下單 (融合舊版 Trader 邏輯)
        """
        contract = self._get_contract()
        if not contract: return False, 0.0, "找不到合約"
        if not self.account: return False, 0.0, "無有效帳號"

        # 1. 動作轉換
        action_enum = constant.Action.Buy if direction == "BUY" else constant.Action.Sell
        
        # 2. 價格類型與委託條件 (關鍵修正！)
        # 如果 Engine 傳來的 price 是 0，或者是某些特定策略要求市價
        # 這裡我們假設: 如果是 DryRun 測試通常會傳 0，或是策略明確指定市價
        
        # V3 策略傳來的 price 通常是 close 價 (限價)
        # 但我們可以設定一個邏輯: 如果 price=0 就打市價
        if price <= 0:
            p_type = constant.FuturesPriceType.MKT
            o_type = constant.OrderType.IOC # 市價必須配 IOC
            input_price = 0
        else:
            p_type = constant.FuturesPriceType.LMT
            o_type = constant.OrderType.ROD # 限價通常配 ROD
            input_price = price

        # 3. Dry Run 攔截
        if self.dry_run:
            msg = f"[Dry Run] 模擬真實下單: {direction} {qty}口 @ {input_price} ({p_type}, {o_type})"
            return True, input_price, msg

        # 4. 真實下單
        try:
            order = self.api.Order(
                price=input_price,
                quantity=qty,
                action=action_enum,
                price_type=p_type,
                order_type=o_type, 
                oct_type=constant.FuturesOCType.Auto, # 自動判斷新平倉
                account=self.account
            )
            
            # print(f"🚀 [Real] 送出訂單: {direction} {qty} @ {input_price}")
            trade = self.api.place_order(contract, order)
            
            # 這裡簡單回傳委託成功，實際上可能要等 callback
            msg = f"[Real] 委託成功 ID: {trade.order.id}"
            return True, input_price, msg

        except Exception as e:
            return False, 0.0, f"API Error: {e}"

    def get_balance(self):
        """查詢權益數 (使用舊版 margin 邏輯)"""
        try:
            if not self.account: return 0
            # 使用 api.margin 查詢期貨權益
            margin = self.api.margin(self.account)
            # 強制轉 float
            equity = float(margin.equity)
            return int(equity)
        except Exception as e:
            print(f"❌ 查詢餘額失敗: {e}")
            return 0

    def get_position(self):
        """查詢真實持倉 (使用舊版 list_positions 邏輯)"""
        try:
            if not self.account: return 0
            
            positions = self.api.list_positions(self.account)
            total_qty = 0
            
            for p in positions:
                if "TMF" in p.code:
                    qty = int(p.quantity) # 強制轉 int
                    if p.direction == constant.Action.Sell:
                        qty = -qty
                    total_qty += qty
            return total_qty
        except Exception as e:
            print(f"❌ 查詢持倉失敗: {e}")
            return 0
        
    def get_real_cost(self):
        """
        向永豐 API 查詢目前部位的真實平均成本
        回傳: float (平均成本價)
        """
        try:
            if not self.account: return 0.0
            
            positions = self.api.list_positions(self.account)
            total_cost = 0.0
            total_qty = 0
            
            for p in positions:
                if "TMF" in p.code: # 確保是我們關注的微型台指期
                    qty = int(p.quantity)
                    price = float(p.price) # 永豐 API 回傳的真實成本價
                    
                    total_qty += qty
                    total_cost += (price * qty)
            
            # 如果有部位，計算加權平均成本
            if total_qty > 0:
                return total_cost / total_qty
            else:
                return 0.0
                
        except Exception as e:
            print(f"❌ 查詢真實成本失敗: {e}")
            return 0.0