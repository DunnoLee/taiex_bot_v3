import shioaji as sj
from config.settings import Settings
from datetime import datetime, timedelta
import pandas as pd

class ShioajiFeeder:
    """
    Shioaji 行情餵食機 V4.0 (含回補功能)
    新增: fetch_kbars 用於補齊歷史斷層數據
    """
    def __init__(self, api: sj.Shioaji):
        self.api = api
        self.on_tick_callback = None
        self.on_bar_callback = None # 雖然主要餵 Tick，但預留 Bar 介面
        self.target_code = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
        self.contract = None
        
        # 綁定 API 的 callback 到自己的處理函式
        self.api.quote.set_on_tick_fop_v1_callback(self._on_tick_arrived)

    def set_on_tick(self, callback):
        """設定 Tick 接收者 (通常是 Aggregator)"""
        self.on_tick_callback = callback

    def set_on_bar(self, callback):
        self.on_bar_callback = callback

    def connect(self):
        """
        Feeder 連線
        (因為 api 是外部傳入且已連線，這裡主要用來確認合約是否存在)
        """
        print(f"🔌 [Feeder] 準備訂閱行情: {self.target_code}")
        
        # 嘗試解析合約 (使用簡易版邏輯，或與 Executor 共用)
        # 這裡我們直接用與 RealExecutor 類似的邏輯找合約
        try:
            # 1. 簡易解析: TMF202603 -> TMFC6
            code = self._resolve_code(self.target_code)
            self.contract = self.api.Contracts.Futures.TMF[code]
            print(f"📄 [Feeder] 鎖定行情合約: {self.contract.name} ({self.contract.code})")
        except Exception as e:
            print(f"❌ [Feeder] 找不到合約 {self.target_code}: {e}")

    def fetch_kbars(self, start_date: str) -> list:
        """
        [新增功能] 從 API 抓取歷史/近期 K 棒 (1分K)
        :param start_date: 字串格式 'YYYY-MM-DD'
        :return: list of dict [{'datetime':..., 'close':...}, ...]
        """
        if not self.contract:
            print("❌ [Feeder] 無合約物件，無法抓取 K 棒")
            return []

        print(f"🔄 [Feeder] 正在向永豐 API 請求 K 棒 (Start: {start_date})...")
        
        try:
            # 呼叫 Shioaji kbars API
            kbars = self.api.kbars(
                contract=self.contract, 
                start=start_date, 
                end=datetime.now().strftime("%Y-%m-%d") # 抓到今天
            )
            
            # 轉成 DataFrame
            df = pd.DataFrame({**kbars})
            if df.empty:
                print("⚠️ [Feeder] API 回傳無資料")
                return []

            # 轉換時間欄位 (ts 是奈秒 timestamp)
            df.ts = pd.to_datetime(df.ts)
            
            # 轉換欄位名稱以符合 BarEvent 標準
            df.rename(columns={
                'ts': 'datetime', 
                'Open': 'open', 
                'High': 'high', 
                'Low': 'low', 
                'Close': 'close', 
                'Volume': 'volume'
            }, inplace=True)

            # 轉成 list of dict
            result_list = df.to_dict('records')
            print(f"✅ [Feeder] 成功取得 {len(result_list)} 根 K 棒")
            
            return result_list

        except Exception as e:
            print(f"❌ [Feeder] 抓取 K 棒失敗: {e}")
            return []
        
    def subscribe(self, symbol=None):
        """開始訂閱"""
        if not self.contract:
            print("❌ [Feeder] 無合約物件，無法訂閱")
            return

        print(f"📡 [Feeder] 訂閱即時報價 (L1): {self.contract.code}")
        try:
            self.api.quote.subscribe(
                self.contract, 
                quote_type=sj.constant.QuoteType.Tick,
                version=sj.constant.QuoteVersion.v1
            )
        except Exception as e:
            print(f"❌ [Feeder] 訂閱失敗: {e}")

    def start(self):
        """啟動 (對於 Shioaji 來說，subscribe 後就開始了，這裡只是佔位符)"""
        pass

    def stop(self):
        """停止"""
        if self.contract:
            print(f"🔕 [Feeder] 取消訂閱: {self.contract.code}")
            try:
                self.api.quote.unsubscribe(self.contract, quote_type=sj.constant.QuoteType.Tick)
            except:
                pass

    def _on_tick_arrived(self, exchange, tick):
        """
        Shioaji 回傳的原始 Tick 處理
        """
        # 確保有 callback 對象
        if not self.on_tick_callback:
            return

        # 過濾商品 (只處理我們訂閱的)
        if self.contract and tick.code != self.contract.code:
            return

        # 轉換資料格式 (Raw -> Standard Dict)
        # Shioaji Tick 結構: {close, volume, datetime...}
        try:
            # 注意: tick.close 可能是 Decimal
            price = float(tick.close)
            qty = int(tick.volume)
            
            # 時間處理 (tick.datetime 是 datetime 物件)
            tick_time = tick.datetime
            
            # 包裝成簡單的 Dict 傳給 Aggregator
            tick_data = {
                'datetime': tick_time,
                'price': price,
                'volume': qty,
                'bid': float(tick.bid_price) if hasattr(tick, 'bid_price') else price, # 選填
                'ask': float(tick.ask_price) if hasattr(tick, 'ask_price') else price  # 選填
            }
            
            # 送出
            self.on_tick_callback(tick_data)
            
        except Exception as e:
            # 避免因為一個壞 tick 導致程式崩潰，印出錯誤但不中斷
            # print(f"⚠️ [Feeder] Tick 解析錯誤: {e}")
            pass

    def _resolve_code(self, target_str):
        """簡易合約代碼轉換 (與 Executor 邏輯一致)"""
        try:
            if len(target_str) < 9: return target_str
            symbol = target_str[:3]
            year_str = target_str[3:7]
            month_str = target_str[7:]
            month_map = {"01":"A", "02":"B", "03":"C", "04":"D", "05":"E", "06":"F", "07":"G", "08":"H", "09":"I", "10":"J", "11":"K", "12":"L"}
            month_code = month_map.get(month_str)
            year_code = year_str[-1]
            return f"{symbol}{month_code}{year_code}"
        except: return target_str