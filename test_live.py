import time
from modules.shioaji_feeder import ShioajiFeeder
from core.event import TickEvent

def on_tick(event: TickEvent):
    print(f"📡 [即時] {event.timestamp} | ${event.price} | Vol: {event.volume}")

def main():
    print("🚀 TaiEx Bot V3 (LIVE Connection Test)")
    
    feeder = ShioajiFeeder()
    feeder.connect()
    
    # 訂閱 TMF (微台)
    feeder.subscribe("TMF")
    
    # 綁定
    feeder.set_on_tick(on_tick)
    
    try:
        # 讓程式跑 10 秒鐘，看看有沒有報錯 (休市期間不會有 tick，但應該顯示訂閱成功)
        for i in range(10):
            time.sleep(1)
            print(f"⏳ 等待行情... {i+1}/10")
    except KeyboardInterrupt:
        pass
    finally:
        feeder.stop()

if __name__ == "__main__":
    main()