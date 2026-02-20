import sys
import time
import shioaji as sj
import threading
from config.settings import Settings
from modules.real_executor import RealExecutor
from modules.shioaji_feeder import ShioajiFeeder
from core.engine import BotEngine
from strategies.ma_strategy import MAStrategy
from strategies.smart_hold_strategy import SmartHoldStrategy
def main():
    # my_strategy = MAStrategy(
    #     fast_window=30, 
    #     slow_window=240, 
    #     stop_loss=300.0,
    #     threshold=5.0,
    #     resample=5
    # )
    my_strategy = SmartHoldStrategy()
    print(f"🧠 [策略] 載入模組: {my_strategy.name}")

    print(f"🚀 TaiEx Bot V3 [Live Mode] 啟動中...")
    print(f"==========================================")

    # -----------------------------------------------------
    # 1. 建立 Shioaji 連線
    # -----------------------------------------------------
    print("🔌 [系統] 正在連線 Shioaji API...")
    api = sj.Shioaji()
    try:
        api.login(
            api_key=Settings.SHIOAJI_API_KEY, 
            secret_key=Settings.SHIOAJI_SECRET_KEY
        )
        print("✅ [系統] API 連線成功！")
    except Exception as e:
        print(f"❌ [系統] API 連線失敗: {e}")
        sys.exit(1)

    # -----------------------------------------------------
    # 2. 初始化 真實執行器 (RealExecutor)
    # -----------------------------------------------------
    # 這裡的 dry_run 取決於 .env 設定，這是你的最後一道保險
    print(f"🛡️ [系統] 交易模式: {'DRY RUN (模擬演習)' if Settings.DRY_RUN else 'LIVE (真槍實彈)'}")
    
    try:
        # RealExecutor 會自動掃描帳號、載入憑證(如果是Live)
        executor = RealExecutor(api, dry_run=Settings.DRY_RUN)
    except SystemExit:
        print("💀 [系統] Executor 初始化失敗，程式終止。")
        sys.exit(1)

    if not executor.account:
        print("❌ [系統] 無法綁定期貨帳號，請檢查帳戶狀態。")
        sys.exit(1)

    print(f"💳 [帳號] 綁定成功: {executor.account.account_id}")
    print(f"💰 [權益] 目前權益數: ${executor.get_balance():,}")

    # -----------------------------------------------------
    # 3. 初始化 行情餵食 (ShioajiFeeder)
    # -----------------------------------------------------
    feeder = ShioajiFeeder(api)

    # -----------------------------------------------------
    # 4. 啟動 機器人引擎 (Engine)
    # -----------------------------------------------------
    # Engine 會把 Feeder 的 Tick 轉成 Bar，再餵給策略，最後叫 Executor 下單
    target_symbol = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
    bot = BotEngine(strategy=my_strategy, feeder=feeder, executor=executor, symbol=target_symbol)

# =====================================================
    # 🛡️ 實戰核心防護：綁定「券商成交回報」監聽器 (自動對帳)
    # =====================================================
    def on_order_event(update_info, update_events):
        """
        處理 Shioaji 的訂單狀態回報 (包含 Deal 成交、Cancel 刪單等)
        """
        try:
            # 取得回報的狀態字串
            status = getattr(update_info, 'status', str(update_info))
            status_str = str(status)
            
            # 偵測到「完全成交 (Filled)」或「部分成交 (PartFilled)」或「Deal」
            if "Filled" in status_str or "Deal" in status_str:
                print(f"\n⚡️ [API 回報] 偵測到真實成交事件！啟動背景同步對帳機制...")
                
                # 開啟一個背景小工人，絕對不卡住 API 回報接收的 Thread
                def _delayed_sync():
                    # 稍微等 1.5 秒，確保券商後端的部位表已經結算更新完畢
                    time.sleep(1.5)
                    
                    try:
                        # 1. 從券商抓取最新的真實倉位
                        real_pos = executor.get_position()
                        
                        # 2. 強制更新策略與 Executor 的「影子帳本」
                        old_pos = bot.strategy.position
                        bot.strategy.set_position(real_pos)
                        executor.current_position = real_pos
                        
                        # 3. 發送 Telegram 報告 (如果 Commander 已經就緒)
                        msg = f"🔄 **真實成交回報同步**\n舊倉位: {old_pos}\n新倉位: {real_pos} (已對齊券商)"
                        if hasattr(bot, 'commander') and bot.commander:
                            bot.commander.send_message(msg)
                        print(f"✅ {msg.replace('**', '')}")
                        
                    except Exception as e:
                        print(f"❌ [同步回報失敗] {e}")

                # 啟動背景同步執行緒
                threading.Thread(target=_delayed_sync, daemon=True).start()
                
        except Exception as e:
            print(f"⚠️ 處理 API 回報發生錯誤: {e}")

    # 正式將監聽器綁定給 Shioaji API
    api.set_order_callback(on_order_event)
    # =====================================================

    # -----------------------------------------------------
    # 5. 數據預載 (Warm-up) - 雙軌機制的第一步
    # -----------------------------------------------------
    print("\n📂 [資料] 正在載入歷史資料 (Cold Data)...")
    # 這裡先讀 CSV，讓 MA 線有基礎
    bot.load_warmup_data("data/history/TMF_History.csv")

    # TODO: 未來這裡要加入 Step 5.5: API Backfill (溫數據)
    # bot.fetch_missing_bars_from_api() 

    # -----------------------------------------------------
    # 6. 正式開跑
    # -----------------------------------------------------
    print("\n🟢 [系統] 引擎啟動，開始監聽行情...")
    bot.start() 
    # bot.start() 內部會啟動 feeder，並進入無窮迴圈(如果是 Live 模式)
    # 除非遇到 Ctrl+C 或 /kill 指令

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 [系統] 使用者強制中斷")
        sys.exit(0)