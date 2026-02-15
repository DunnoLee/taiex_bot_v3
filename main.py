import sys
from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder
from core.event import TickEvent, BarEvent

# 定義兩個簡單的回呼函數 (Callback) 來模擬策略接收資料
def on_tick_received(event: TickEvent):
    # 只印出部分，避免洗版
    # print(f"Tick: {event.price}") 
    pass

def on_bar_received(event: BarEvent):
    print(f"📊 [K線完成] {event.timestamp} | Open: {event.open} | Close: {event.close} | Vol: {event.volume}")

def main():
    print(f"🚀 TaiEx Bot V3 (K-Bar Mode) 啟動...")
    print(f"檔案: data_sample.csv")
    
    # 1. 初始化 Mock Feeder (速度設為 0.05 秒一根，方便觀察)
    feeder = CsvHistoryFeeder("data_sample.csv", speed=0.05)
    
    # 2. 連線
    feeder.connect()
    
    # 3. 綁定策略 (告訴 Feeder 資料要送給誰)
    feeder.set_on_tick(on_tick_received)
    feeder.set_on_bar(on_bar_received)
    
    # 4. 開始回放
    feeder.start()

if __name__ == "__main__":
    main()