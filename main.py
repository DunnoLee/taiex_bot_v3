import sys
from config.settings import Settings
from core.event import EventType

def main():
    print(f"🚀 TaiEx Bot V3 啟動中...")
    print(f"📌 監控標的: {Settings.SYMBOL_CODE}")
    print(f"⚙️  策略參數: MA_Fast={Settings.STRATEGY_MA_FAST}, MA_Slow={Settings.STRATEGY_MA_SLOW}")
    
    try:
        # 這裡未來會初始化 DataFeeder, Strategy, EventEngine
        print("✅ 設定載入成功，準備進入事件迴圈...")
        
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()