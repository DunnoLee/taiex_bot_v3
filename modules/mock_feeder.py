import time
import pandas as pd
from datetime import datetime
from typing import Callable, Optional
from core.data_feeder import DataFeeder
from core.event import TickEvent, BarEvent, EventType
from config.settings import Settings

class CsvHistoryFeeder(DataFeeder):
    """
    讀取歷史 CSV 檔案 (K-Bar 格式)，模擬行情推送。
    支援格式: Time, Open, High, Low, Close, Volume, Amount
    """
    def __init__(self, file_path: str, speed: float = 0.01):
        super().__init__()
        self.file_path = file_path
        self.speed = speed  # 播放間隔 (秒)，越小越快
        self.running = False
        self.df = None

    def connect(self):
        print(f"📂 [Mock] 正在讀取歷史 K 線檔案: {self.file_path}...")
        try:
            # 讀取 CSV
            self.df = pd.read_csv(self.file_path)
            
            # 處理時間欄位: 你的 CSV 只有 'Time' 欄位，包含日期與時間
            if 'Time' in self.df.columns:
                self.df['Datetime'] = pd.to_datetime(self.df['Time'])
            else:
                print("❌ CSV 格式錯誤: 找不到 'Time' 欄位")
                return

            # 確保按照時間排序
            self.df = self.df.sort_values('Datetime').reset_index(drop=True)
            
            print(f"✅ 讀取完成，共 {len(self.df)} 根 K 棒。")
            print(f"📅 資料範圍: {self.df['Datetime'].iloc[0]} -> {self.df['Datetime'].iloc[-1]}")
            
        except Exception as e:
            print(f"❌ 讀取失敗: {e}")

    def subscribe(self, symbol: str):
        # Mock 模式下，這只是個形式，實際上是看 CSV 裡有什麼
        pass

    def start(self):
        if self.df is None:
            print("❌ 無資料可播放，請先執行 connect()")
            return

        self.running = True
        print(f"▶️ [Mock] 開始回放 K 棒資料...")

        # 使用 iterrows 逐行讀取 (雖然慢但最接近模擬行為)
        for index, row in self.df.iterrows():
            if not self.running: break

            current_time = row['Datetime']
            close_price = float(row['Close'])

            # 1. 建立 BarEvent (這是主角)
            bar_event = BarEvent(
                symbol=Settings.SYMBOL_CODE,
                period="1m", # 假設你的 CSV 是 1 分 K
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=close_price,
                volume=int(row['Volume']),
                timestamp=current_time
            )

            # 2. 建立偽造的 TickEvent (配角)
            # 有些策略可能依賴 Tick 更新，我們用 K 棒的收盤價 "偽裝" 成一個 Tick
            tick_event = TickEvent(
                symbol=Settings.SYMBOL_CODE,
                price=close_price,
                volume=int(row['Volume']),
                bid_price=close_price,
                ask_price=close_price,
                timestamp=current_time,
                simulated=True
            )

            # 3. 推送事件 (先推 Tick，再推 Bar，模擬真實順序)
            if self.on_tick_callback:
                self.on_tick_callback(tick_event)
            
            if self.on_bar_callback:
                self.on_bar_callback(bar_event)

            # 4. 控制播放速度
            if self.speed > 0:
                time.sleep(self.speed)

        self.running = False
        print("🏁 [Mock] 回放結束")

    def stop(self):
        self.running = False