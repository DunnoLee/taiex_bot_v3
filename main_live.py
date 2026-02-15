import time
import sys
from config.settings import Settings
from modules.shioaji_feeder import ShioajiFeeder
from modules.ma_strategy import MAStrategy
from modules.commander import TelegramCommander  # <--- 新增
from core.aggregator import BarAggregator
from core.event import BarEvent, SignalEvent

def main():
    print(f"🚀 TaiEx Bot V3 (LIVE TRADING) 啟動...")
    print(f"==========================================")
    
    # 1. 初始化指揮官 (通知系統)
    commander = TelegramCommander()
    
    # 2. 初始化核心元件
    feeder = ShioajiFeeder()
    strategy = MAStrategy()
    
    # 連線與訂閱
    try:
        feeder.connect()
        feeder.subscribe("TMF") 
        
        # 等待合約代碼確認
        time.sleep(2)
        if not feeder.target_code:
            print("❌ 無法取得合約代碼，程式終止")
            commander.send_message("❌ **系統啟動失敗**: 無法取得合約代碼")
            sys.exit(1)
            
        # 初始化合成器
        aggregator = BarAggregator(symbol=feeder.target_code)
        
        # 發送啟動成功通知 (這時候你的手機應該要響！)
        commander.send_startup_report(feeder.target_code, strategy.name)
        
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        commander.send_message(f"❌ **系統崩潰**: {e}")
        sys.exit(1)

    # 3. 定義資料流 Callback
    def on_strategy_signal(signal: SignalEvent):
        if not signal: return
        
        print(f"\n⚡️ [訊號] {signal.signal_type} | {signal.reason}")
        
        # 發送訊號通知到手機
        commander.send_signal_notification(signal)
        
        # TODO: 下一階段接 RealExecutor 下單

    def on_bar_generated(bar: BarEvent):
        # 顯示 K 棒進度
        print(f"📊 [Live] {bar.timestamp.strftime('%H:%M')} C:{bar.close} V:{bar.volume}", end='\r')
        
        signal = strategy.on_bar(bar)
        if signal:
            on_strategy_signal(signal)

    # 4. 綁定事件
    feeder.set_on_tick(aggregator.on_tick)
    aggregator.set_on_bar(on_bar_generated)

    print(f"✅ 系統就緒！正在監聽 {feeder.target_code}...")
    print(f"🧠 策略暖機中 (需 {strategy.slow_window} 根 K 棒)...")

    # 5. 保持執行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 系統關閉")
        commander.send_message("🛑 **系統已手動關閉**")
        feeder.stop()

if __name__ == "__main__":
    main()