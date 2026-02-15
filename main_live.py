import time
import sys
from config.settings import Settings
from modules.shioaji_feeder import ShioajiFeeder
from modules.ma_strategy import MAStrategy
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent

def main():
    print(f"🚀 TaiEx Bot V3 (LIVE TRADING) 啟動...")
    print(f"==========================================")
    
    # 1. 初始化三大元件
    feeder = ShioajiFeeder()
    strategy = MAStrategy() # 預設讀取 Settings 的 10/240
    
    # 先連線才能知道我們要訂閱什麼代碼 (target_code)
    feeder.connect()
    feeder.subscribe("TMF") # 訂閱微台
    
    # 等待一下，確保 feeder.target_code 有抓到 (例如 TMFB6)
    time.sleep(2)
    if not feeder.target_code:
        print("❌ 無法取得合約代碼，程式終止")
        sys.exit(1)
        
    # 初始化合成器 (必須知道合約代碼)
    aggregator = BarAggregator(symbol=feeder.target_code)

    # 2. 定義資料流 (Pipeline)
    # 流程: Feeder(Tick) -> Aggregator(Accumulate) -> Strategy(Bar) -> Action
    
    def on_strategy_signal(signal: SignalEvent):
        """處理策略訊號 (下單層)"""
        if not signal: return
        print(f"\n⚡️ [下單訊號] {signal.timestamp} | {signal.signal_type} | {signal.reason}")
        # TODO: 下一階段這裡接 RealExecutor (Shioaji 下單)

    def on_bar_generated(bar: BarEvent):
        """當 Aggregator 完成一根 K 棒時"""
        print(f"📊 [Live Bar] {bar.timestamp.strftime('%H:%M')} | Close: {bar.close} | Vol: {bar.volume}")
        
        # 餵給策略
        signal = strategy.on_bar(bar)
        if signal:
            on_strategy_signal(signal)

    # 3. 綁定事件
    # Feeder 收到 Tick -> 丟給 Aggregator
    feeder.set_on_tick(aggregator.on_tick)
    
    # Aggregator 完成 Bar -> 丟給 on_bar_generated (再轉給策略)
    aggregator.set_on_bar(on_bar_generated)

    print(f"✅ 系統就緒！正在監聽 {feeder.target_code} 的即時行情...")
    print(f"🧠 策略暖機中 (需累積 {strategy.slow_window} 根 K 棒)...")

    # 4. 保持執行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 系統關閉")
        feeder.stop()

if __name__ == "__main__":
    main()