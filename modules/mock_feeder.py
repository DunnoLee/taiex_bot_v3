import pandas as pd
import time
import threading
from core.event import BarEvent, EventType

class CsvHistoryFeeder:
    """
    CsvHistoryFeeder (模擬行情餵食機) - V3.91 Event Fix
    
    修正:
    1. BarEvent 實例化移除 'event_type' 參數 (由類別內部自動處理)。
    2. 維持 threading 背景執行。
    """
    def __init__(self, file_path, speed=0.5):
        self.file_path = file_path
        self.speed = speed
        self.df = None
        self.running = False
        self.target_code = "TMF_SIM"
        
        self.on_bar_callback = None
        self.on_tick_callback = None 

    def connect(self):
        print(f"🔌 [Sim] 正在讀取歷史資料: {self.file_path}...")
        try:
            self.df = pd.read_csv(self.file_path)
            self.df.columns = self.df.columns.str.strip() # 去除空白
            
            # 欄位映射
            rename_map = {
                'Time': 'datetime', 'time': 'datetime', 'Date': 'datetime',
                'Open': 'open',     'open': 'open',
                'High': 'high',     'high': 'high',
                'Low': 'low',       'low': 'low',
                'Close': 'close',   'close': 'close',
                'Volume': 'volume', 'volume': 'volume', 'Vol': 'volume'
            }
            self.df.rename(columns=rename_map, inplace=True)
            
            if 'datetime' in self.df.columns:
                self.df['datetime'] = pd.to_datetime(self.df['datetime'])
                self.df.sort_values('datetime', inplace=True)
                self.df.reset_index(drop=True, inplace=True)
                print(f"✅ [Sim] 資料載入成功，共 {len(self.df)} 筆")
            else:
                print(f"❌ [Sim] CSV 缺少時間欄位")
                self.df = pd.DataFrame()
            
        except Exception as e:
            print(f"❌ [Sim] 讀取 CSV 失敗: {e}")
            self.df = pd.DataFrame()

    def subscribe(self, symbol):
        self.target_code = symbol
        print(f"📡 [Sim] 模擬訂閱: {symbol}")

    def set_on_tick(self, callback):
        pass

    def set_on_bar(self, callback):
        self.on_bar_callback = callback

    def start(self):
        if self.df is None or self.df.empty:
            print("⚠️ [Sim] 無資料可回放")
            return

        self.running = True
        print(f"▶️ [Sim] 開始回放 (速度: {self.speed}s/bar)...")
        
        t = threading.Thread(target=self._run_loop)
        t.daemon = True 
        t.start()

    def stop(self):
        self.running = False
        print("🛑 [Sim] 停止回放")

    def _run_loop(self):
        """背景回放迴圈"""
        #for index, row in self.df.iterrows():
        for row in self.df.itertuples(index=False):
            if not self.running: break
            
            # 修正點：移除 event_type 參數
            # 假設 BarEvent 的定義是 (symbol, timestamp, open, high, low, close, volume)
            # 如果還有其他參數 (如 open_interest)，請依據 core/event.py 補上
            try:
                # 注意：itertuples 回傳的是屬性，所以原本的 row['close'] 要改成 row.close
                bar = BarEvent(
                    symbol=self.target_code,
                    timestamp=row.datetime,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume
                )

                # bar = BarEvent(
                #     symbol=self.target_code,
                #     timestamp=row['datetime'],
                #     open=row['open'],
                #     high=row['high'],
                #     low=row['low'],
                #     close=row['close'],
                #     volume=row['volume']
                # )
                
                if self.on_bar_callback:
                    # 這裡可以簡單印出時間，確認有在跑
                    # print(f"⏳ [Sim] {bar.timestamp} C:{int(bar.close)}")
                    self.on_bar_callback(bar)
            
            except TypeError as e:
                print(f"❌ [Sim] BarEvent 參數錯誤: {e}")
                self.running = False
                break
            
            if self.speed > 0:
                time.sleep(self.speed)
            
        print("\n🏁 [Sim] 回放結束")
        self.running = False